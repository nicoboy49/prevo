"""Chantier multilingue, Lot 4 — langue de l'installation, langue_defaut (T295 ; D148, D149, D156 ; ARCHITECTURE.md §24.11).

Dans Chromium, mode serveur (serveur.py sur une copie du jeu de démo, profil responsable), sauf mention :
    - réglage « Langue de l'installation » (Paramètres, section Entreprise) : les langues déclarées sous leur nom dans
      leur langue, « fr » par défaut ; English enregistré → langue_defaut = en dans parametres.csv, page rechargée en
      anglais (poste sans choix), réglage relu ; retour au français ;
    - poste sans choix, langue_defaut = en sur le disque : l'anglais d'emblée, sans rechargement (T297 : serveur.py pose
      la langue de l'installation dans index.html, data-langue-installation) ; clé « prevo.langue.installation »
      écrite ; un rechargement de plus : aucun autre ;
    - poste avec choix : choisi Français dans une installation anglaise, il le garde (clé « prevo.langue » = fr) ;
      English, la langue de l'installation, retire la clé (le poste la suit) ;
    - valeurs inconnues (langue_defaut « de », clés du navigateur « zz » et mal formée) : ignorées, français, aucun
      rechargement ni requête d'une autre langue ;
    - pas de boucle : page servie sans la langue de l'installation (attribut retiré) et clé de l'installation refusée
      par le navigateur → un seul rechargement, puis la page reste en français, avec un avertissement ; textes des
      données en français faute du dictionnaire anglais, sans erreur ; avec l'attribut, la même clé refusée : l'anglais
      d'emblée, aucun rechargement (T297) ;
    - données (inventaire : commentaire et utilisateur du mouvement, profil du journal) dans la langue de
      l'installation, quelle que soit la langue affichée : installation en + écran fr, installation en + écran en,
      installation fr + écran en ;
    - démo (file://) : la langue de l'installation retenue par le navigateur sert à l'affichage, celle de la démo aux
      données ; rien n'est retenu ni rechargé ;
    - base neuve par l'écran « base vide » (T296) : liste « Langue de Prévo » (noms dans leur langue), proposée d'après
      le navigateur ; serveur sans base, navigateur fr-FR, English choisi puis la démo : parametres.csv = lignes de la
      démo + langue_defaut = en, un rechargement, l'anglais ; mode dossier (OPFS), navigateur en-GB : English proposé,
      base vide avec version_schema et langue_defaut = en, aucun rechargement.
Les textes attendus sont lus dans js/i18n/fr.js et js/i18n/en.js, pas par le moteur.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_langue_installation.py" -v
"""
import csv
import io
import re
import time
import unittest
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)

BOM = "﻿"
# Base neuve (T296) : Chromium note en console.error les 404 attendus (CSV absents, pas de /api/ping en statique).
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")
NOM_DOSSIER_SIMULE = "donnees-test"
LISTE_BASE_VIDE_JS = """() => {
  const liste = document.querySelector('#ecran-base-vide #base-vide-langue');
  const bloc = liste.closest('.champ');
  return { options: [...liste.options].map((o) => [o.value, o.textContent, o.lang]), valeur: liste.value,
    libelle: bloc.querySelector('label').textContent.trim(), aide: bloc.querySelector('.aide').textContent.trim() };
}"""
LIRE_OPFS_JS = """async ([dossier, fichier]) => {
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(dossier);
  return (await (await racine.getFileHandle(fichier)).getFile()).text();
}"""
FORMULAIRE = "#form-parametres "
CHAMP_LANGUE = FORMULAIRE + "[name=langue_defaut]"
POSTE_LANGUE = "#poste-langue-liste"
ATTENTE_SANS_RECHARGEMENT_MS = 1500     # temps laissé à un rechargement de trop pour se produire

# État de la langue dans la page.
ETAT_JS = """() => {
  const lire = (stockage, cle) => { try { return stockage.getItem(cle); } catch (erreur) { return 'illisible'; } };
  return { langue: I18n.langue, lang: document.documentElement.lang, installation: I18n.installation,
    donnees: I18n.langueDesDonnees, poste: lire(localStorage, 'prevo.langue'),
    retenue: lire(localStorage, 'prevo.langue.installation'), raison: lire(sessionStorage, 'prevo.langue.rechargement') };
}"""
# Choix du poste posé une seule fois par onglet (sessionStorage), pour que le sélecteur puisse ensuite le changer.
CHOIX_UNE_FOIS_JS = """(() => {
  try {
    if (!sessionStorage.getItem('test.choix')) {
      sessionStorage.setItem('test.choix', '1');
      %s
    }
  } catch (erreur) { /* sans stockage : rien */ }
})();"""
# Le navigateur refuse la seule clé de la langue de l'installation (le reste de Prévo garde son stockage).
REFUS_INSTALLATION_JS = """(() => {
  const avant = Storage.prototype.setItem;
  Storage.prototype.setItem = function (cle, ...reste) {
    if (cle === 'prevo.langue.installation') throw new DOMException('Stockage refusé (test)', 'SecurityError');
    return avant.call(this, cle, ...reste);
  };
})();"""
# Inventaire d'un article sans commentaire : Prévo écrit le commentaire et l'utilisateur (D156).
INVENTAIRE_JS = """async () => {
  const article = Donnees.lignes('articles')[0];
  await Magasin.inventorier([{ articleId: article.id, quantite: 7 }], '');
  return article.id;
}"""


def texte_du_dictionnaire(code, cle):
    """Valeur de `cle` dans js/i18n/<code>.js, lue dans le fichier (échappements « \\' » retirés)."""
    source = (RACINE / "js" / "i18n" / (code + ".js")).read_text(encoding="utf-8")
    trouve = re.search(r"^  '%s': '((?:[^'\\]|\\.)*)',$" % re.escape(cle), source, re.MULTILINE)
    if not trouve:
        raise AssertionError("clé %s absente de js/i18n/%s.js" % (cle, code))
    return re.sub(r"\\(.)", r"\1", trouve.group(1))


def lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, delimiter=";")
        entete = next(lecteur)
        return entete, [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


def poser_langue(dossier, valeur):
    """langue_defaut = valeur dans parametres.csv (ligne remplacée ou ajoutée), écrit comme Prévo l'écrit."""
    chemin = Path(dossier) / "parametres.csv"
    entete, lignes = lire_csv(chemin)
    lignes = [ligne for ligne in lignes if ligne["cle"] != "langue_defaut"] + [{"cle": "langue_defaut", "valeur": valeur}]
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    for ligne in lignes:
        ecrivain.writerow([ligne.get(nom, "") for nom in entete])
    chemin.write_bytes((BOM + tampon.getvalue()).encode("utf-8"))


def parametre_sur_le_disque(dossier, cle):
    _, lignes = lire_csv(Path(dossier) / "parametres.csv")
    valeurs = [ligne["valeur"].lstrip("'") for ligne in lignes if ligne["cle"] == cle]
    return valeurs[-1] if valeurs else None


class TestLangueInstallation(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.chargements = 0
        self.page.on("load", self._compter)
        self.avertissements = []
        self.page.on("console", lambda message: self.avertissements.append(message.text)
                     if message.type == "warning" else None)
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))

    def _compter(self, _page):
        self.chargements += 1

    # -- outils ---------------------------------------------------------------------------------

    def attendre_chargements(self, nombre, delai_s=15):
        """Attend le `nombre`-ième chargement de la page, puis l'application prête ; aucun chargement de plus ensuite."""
        fin = time.monotonic() + delai_s
        while self.chargements < nombre:
            if time.monotonic() > fin:
                self.fail("%d chargement(s) de la page au lieu de %d" % (self.chargements, nombre))
            self.page.wait_for_timeout(100)
        attendre_pret(self.page)
        self.page.wait_for_timeout(ATTENTE_SANS_RECHARGEMENT_MS)
        self.assertEqual(self.chargements, nombre, "rechargement de trop")

    def ouvrir(self, serveur, route="#/accueil", chargements=1):
        self.page.goto(serveur.url + "/" + route)
        self.attendre_chargements(chargements)
        return self.etat()

    def etat(self):
        return self.page.evaluate(ETAT_JS)

    def choisir_au_poste(self, code, chargements):
        self.page.evaluate("location.hash = '#/poste'")
        self.page.wait_for_selector(POSTE_LANGUE)
        with self.page.expect_navigation():
            self.page.select_option(POSTE_LANGUE, code)
        self.attendre_chargements(chargements)
        return self.etat()

    def inventorier(self, serveur):
        """Inventaire sans commentaire ; (commentaire, utilisateur) du mouvement et profil du journal, lus sur le disque."""
        article = self.page.evaluate(INVENTAIRE_JS)
        _, mouvements = lire_csv(serveur.dossier / "mouvements_stock.csv")
        mouvement = [m for m in mouvements if m["type"] == "inventaire" and m["article_id"] == article][-1]
        _, journal = lire_csv(serveur.dossier / "journal.csv")
        ligne = [j for j in journal if j["table"] == "mouvements_stock" and j["id_ligne"] == mouvement["id"]][-1]
        return mouvement["commentaire"], mouvement["utilisateur"], ligne["profil"]

    def attendus(self, code):
        return (texte_du_dictionnaire(code, "magasin.inventorier.inventaire"),
                texte_du_dictionnaire(code, "magasin.utilisateur_courant.responsable"),
                texte_du_dictionnaire(code, "socle.libelle_type.responsable"))

    # -- tests ----------------------------------------------------------------------------------

    def test_reglage_enregistre_dans_parametres_csv_et_relu(self):
        with ServeurPrevo() as serveur:
            self.assertIsNone(parametre_sur_le_disque(serveur.dossier, "langue_defaut"))     # absente de la démo
            self.ouvrir(serveur, "#/parametres")
            self.page.wait_for_selector(CHAMP_LANGUE)
            champ = self.page.evaluate("""(selecteur) => {
              const liste = document.querySelector(selecteur);
              const bloc = liste.closest('.champ');
              return { options: [...liste.options].map((o) => [o.value, o.textContent, o.lang]), valeur: liste.value,
                libelle: bloc.querySelector('label').textContent.trim(), aide: bloc.querySelector('.aide').textContent.trim(),
                section: [...document.querySelectorAll('#form-parametres > *')].slice(0, 4).map((e) => e.tagName === 'H3'
                  ? 'h3:' + e.textContent.trim() : e.dataset.champ) };
            }""", CHAMP_LANGUE)
            self.assertEqual(champ["options"], [["", "—", ""], ["fr", "Français", "fr"], ["en", "English", "en"]])
            self.assertEqual(champ["valeur"], "fr")                                          # défaut
            self.assertEqual(champ["libelle"], texte_du_dictionnaire("fr", "parametres.libelle.langue_installation"))
            self.assertEqual(champ["aide"], texte_du_dictionnaire("fr", "parametres.aide.langue_proposee_postes_textes"))
            self.assertEqual(champ["section"], ["h3:" + texte_du_dictionnaire("fr", "parametres.section.entreprise"),
                                                "entreprise_nom", "langue_defaut", "devise"])    # devise : T304

            # English enregistré : écrit dans parametres.csv, page rechargée en anglais (ce poste n'a pas de choix).
            self.page.select_option(CHAMP_LANGUE, "en")
            with self.page.expect_navigation():
                self.page.click(FORMULAIRE + "button[type=submit]")
            self.attendre_chargements(2)
            self.assertEqual(parametre_sur_le_disque(serveur.dossier, "langue_defaut"), "en")
            self.assertEqual(self.etat(), {"langue": "en", "lang": "en", "installation": "en", "donnees": "en",
                                           "poste": None, "retenue": "en", "raison": None})
            self.page.wait_for_selector(CHAMP_LANGUE)
            self.assertEqual(self.page.input_value(CHAMP_LANGUE), "en")                       # relu
            self.assertEqual(self.page.inner_text(".champ[data-champ='langue_defaut'] label").strip(),
                             texte_du_dictionnaire("en", "parametres.libelle.langue_installation"))

            # Retour au français : écrit, page rechargée en français.
            self.page.select_option(CHAMP_LANGUE, "fr")
            with self.page.expect_navigation():
                self.page.click(FORMULAIRE + "button[type=submit]")
            self.attendre_chargements(3)
            self.assertEqual(parametre_sur_le_disque(serveur.dossier, "langue_defaut"), "fr")
            self.assertEqual(self.etat(), {"langue": "fr", "lang": "fr", "installation": "fr", "donnees": "fr",
                                           "poste": None, "retenue": "fr", "raison": None})

    def test_poste_sans_choix_langue_de_l_installation_d_emblee(self):
        with ServeurPrevo() as serveur:
            poser_langue(serveur.dossier, "en")
            etat = self.ouvrir(serveur)                         # T297 : la page servie dit l'anglais, aucun rechargement
            self.assertEqual(etat, {"langue": "en", "lang": "en", "installation": "en", "donnees": "en",
                                    "poste": None, "retenue": "en", "raison": None})
            self.assertEqual(self.page.evaluate("document.documentElement.dataset.langueInstallation"), "en")
            self.assertEqual(self.page.evaluate("I18n.t('poste.menu.libelle')"),
                             texte_du_dictionnaire("en", "poste.menu.libelle"))
            # Page rouverte : l'anglais d'emblée, aucun rechargement de plus.
            self.page.reload()
            self.attendre_chargements(2)
            self.assertEqual(self.etat()["langue"], "en")

    def test_poste_avec_choix_garde_son_choix(self):
        self.contexte.add_init_script(CHOIX_UNE_FOIS_JS % "localStorage.setItem('prevo.langue', 'fr');")
        with ServeurPrevo() as serveur:
            poser_langue(serveur.dossier, "en")
            # Français choisi : il reste ; le dictionnaire anglais (textes des données) est chargé d'emblée (T297).
            etat = self.ouvrir(serveur)
            self.assertEqual(etat, {"langue": "fr", "lang": "fr", "installation": "en", "donnees": "en",
                                    "poste": "fr", "retenue": "en", "raison": None})
            # English, la langue de l'installation, choisi à « Ce poste » : la clé est retirée, le poste la suit.
            etat = self.choisir_au_poste("en", 2)
            self.assertEqual((etat["langue"], etat["poste"]), ("en", None))
            # Français choisi de nouveau : retenu (il diffère de l'installation), sans autre rechargement.
            etat = self.choisir_au_poste("fr", 3)
            self.assertEqual((etat["langue"], etat["poste"], etat["donnees"]), ("fr", "fr", "en"))

    def test_valeurs_inconnues_ignorees(self):
        self.contexte.add_init_script(CHOIX_UNE_FOIS_JS % (
            "localStorage.setItem('prevo.langue', 'zz'); "
            "localStorage.setItem('prevo.langue.installation', 'xx\"><img src=x onerror=alert(1)>');"))
        with ServeurPrevo() as serveur:
            poser_langue(serveur.dossier, "de")
            etat = self.ouvrir(serveur, "#/parametres")         # aucun rechargement
            self.assertEqual(etat, {"langue": "fr", "lang": "fr", "installation": "fr", "donnees": "fr",
                                    "poste": "zz", "retenue": "fr", "raison": None})
            autres = [url for url in self.requetes if "/js/i18n/" in url
                      and not re.search(r"/js/i18n/(langues|fr|aide/fr)\.js$", url)]
            self.assertEqual(autres, [])
            # Le réglage montre la valeur du fichier telle quelle (signalée inconnue), sans la remplacer.
            self.page.wait_for_selector(CHAMP_LANGUE)
            self.assertEqual(self.page.input_value(CHAMP_LANGUE), "de")
            self.assertEqual(parametre_sur_le_disque(serveur.dossier, "langue_defaut"), "de")

    def test_pas_de_boucle_de_rechargement(self):
        self.contexte.add_init_script(REFUS_INSTALLATION_JS)
        with ServeurPrevo() as serveur:
            poser_langue(serveur.dossier, "en")
            # Page servie sans la langue de l'installation (T297 : attribut retiré, comme une page d'un ancien serveur) :
            # seule la lecture des paramètres l'apprend.
            def sans_langue_de_la_page(route):
                reponse = route.fetch()
                corps = reponse.text().replace('data-langue-installation="en"', 'data-langue-installation=""')
                route.fulfill(response=reponse, body=corps)
            self.page.route(serveur.url + "/", sans_langue_de_la_page)
            etat = self.ouvrir(serveur, chargements=2)          # un rechargement, puis plus aucun
            self.assertEqual(etat, {"langue": "fr", "lang": "fr", "installation": "en", "donnees": "fr",
                                    "poste": None, "retenue": None, "raison": "en/en"})
            self.assertEqual(len([texte for texte in self.avertissements if "déjà rechargée pour la langue" in texte]), 1)
            # Dictionnaire anglais absent : les textes des données restent en français, sans erreur.
            self.assertEqual(self.inventorier(serveur), self.attendus("fr"))

    def test_langue_donnee_par_la_page_sans_stockage_aucun_rechargement(self):
        """T297 : la page servie dit la langue de l'installation ; la clé refusée par le navigateur ne gêne pas."""
        self.contexte.add_init_script(REFUS_INSTALLATION_JS)
        with ServeurPrevo() as serveur:
            poser_langue(serveur.dossier, "en")
            etat = self.ouvrir(serveur)
            self.assertEqual(etat, {"langue": "en", "lang": "en", "installation": "en", "donnees": "en",
                                    "poste": None, "retenue": None, "raison": None})
            self.assertEqual(self.inventorier(serveur), self.attendus("en"))

    def test_donnees_dans_la_langue_de_l_installation_quelle_que_soit_la_langue_affichee(self):
        cas = (("en", "fr", 1), ("en", None, 1), ("fr", "en", 1))      # installation, choix du poste, chargements
        for installation, choix, chargements in cas:
            with self.subTest(installation=installation, choix=choix):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                self.addCleanup(contexte.close)
                preregler_profil(contexte, "responsable")
                if choix:
                    contexte.add_init_script(CHOIX_UNE_FOIS_JS % ("localStorage.setItem('prevo.langue', %r);" % choix))
                self.page = contexte.new_page()
                self.surveiller(self.page)
                self.chargements = 0
                self.page.on("load", self._compter)
                with ServeurPrevo() as serveur:
                    poser_langue(serveur.dossier, installation)
                    etat = self.ouvrir(serveur, chargements=chargements)
                    self.assertEqual((etat["langue"], etat["installation"], etat["donnees"]),
                                     (choix or installation, installation, installation))
                    self.assertEqual(self.inventorier(serveur), self.attendus(installation))
                    # Ce qui est affiché, lui, suit l'écran.
                    self.assertEqual(self.page.evaluate("I18n.t('magasin.inventorier.inventaire')"),
                                     texte_du_dictionnaire(choix or installation, "magasin.inventorier.inventaire"))

    def test_demo_rien_retenu_ni_recharge(self):
        self.contexte.add_init_script(CHOIX_UNE_FOIS_JS % "localStorage.setItem('prevo.langue.installation', 'en');")
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-demo")
        self.attendre_chargements(1)
        # Affichage : la langue de l'installation retenue par ce navigateur ; données : celle de la démo (français).
        self.assertEqual(self.etat(), {"langue": "en", "lang": "en", "installation": "fr", "donnees": "fr",
                                       "poste": None, "retenue": "en", "raison": None})
        self.assertEqual(self.page.evaluate("I18n.donnees('magasin.inventorier.inventaire')"),
                         texte_du_dictionnaire("fr", "magasin.inventorier.inventaire"))

    # -- T296 : base neuve créée par l'écran « base vide » (mode serveur sans assistant, mode dossier) ------------

    def nouveau_poste(self, locale):
        """Remplace le contexte du test par un navigateur de la langue `locale` (profil responsable mémorisé)."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale=locale, viewport={"width": 1280, "height": 800})
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        preregler_profil(self.contexte, "responsable")
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.chargements = 0
        self.page.on("load", self._compter)

    def liste_base_vide(self):
        self.page.wait_for_selector("#ecran-base-vide", state="visible")
        return self.page.evaluate(LISTE_BASE_VIDE_JS)

    def test_base_vide_serveur_francais_propose_english_choisi_avec_la_demo(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        with ServeurPrevo(source=None) as serveur:
            self.page.goto(serveur.url + "/")
            liste = self.liste_base_vide()
            self.assertEqual(liste["options"], [["fr", "Français", "fr"], ["en", "English", "en"]])
            self.assertEqual(liste["valeur"], "fr")                                          # navigateur fr-FR
            self.assertEqual(liste["libelle"], texte_du_dictionnaire("fr", "socle.ecran_base_vide.langue_prevo"))
            self.assertEqual(liste["aide"], texte_du_dictionnaire("fr", "socle.ecran_base_vide.langue_prevo_aide"))
            self.page.select_option("#base-vide-langue", "en")
            self.page.click("#btn-base-demo")
            self.attendre_chargements(2)                       # la base écrite en anglais : un rechargement
            self.assertEqual(self.etat(), {"langue": "en", "lang": "en", "installation": "en", "donnees": "en",
                                           "poste": None, "retenue": "en", "raison": None})
            # parametres.csv : les lignes du jeu de démo telles quelles, puis la langue choisie.
            _, demo = lire_csv(RACINE / "donnees" / "demo" / "parametres.csv")
            _, lignes = lire_csv(serveur.dossier / "parametres.csv")
            self.assertEqual(lignes, demo + [{"cle": "langue_defaut", "valeur": "en"}])

    def test_base_vide_dossier_navigateur_anglais_english_propose(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        self.nouveau_poste("en-GB")
        installer_dossier_simule(self.contexte, NOM_DOSSIER_SIMULE)
        with ServeurStatique(RACINE) as statique:
            self.page.goto(statique.url + "/index.html")
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.page.click("#btn-dossier")
            liste = self.liste_base_vide()
            self.assertEqual(liste["valeur"], "en")
            self.assertEqual(liste["libelle"], texte_du_dictionnaire("en", "socle.ecran_base_vide.langue_prevo"))
            self.page.click("#btn-base-vide")
            self.attendre_chargements(1)                       # page déjà en anglais : aucun rechargement
            self.assertEqual(self.page.evaluate("App.mode"), "dossier")
            self.assertEqual(self.etat(), {"langue": "en", "lang": "en", "installation": "en", "donnees": "en",
                                           "poste": None, "retenue": "en", "raison": None})
            texte = self.page.evaluate(LIRE_OPFS_JS, [NOM_DOSSIER_SIMULE, "parametres.csv"])
            self.assertEqual(texte.lstrip(BOM).split("\r\n"), ["cle;valeur", "version_schema;'3", "langue_defaut;en", ""])


if __name__ == "__main__":
    unittest.main()
