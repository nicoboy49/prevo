"""Fiche d'accès dans la coque, hors mode serveur (tâche T252 ; js/modules/installation-fiche.js, afficherDansLaCoque).

Défaut corrigé : en démo et en mode dossier, la fiche ajoutait au conteneur le fragment HTML rendu par UI.vide (un
UI.html, pas un nœud) : « Failed to execute 'appendChild' on 'Node' » au lieu du message « Pas de serveur ».

Ce qui est vérifié, dans un navigateur, pour le profil Responsable :
    démo         : index.html en file://, « Essayer avec les données de démo » ;
    mode dossier : index.html servi par un petit serveur de fichiers (tests/commun.py ServeurStatique), dossier simulé
                   dans l'OPFS (installer_dossier_simule), base de démo copiée dedans ;
    dans les deux : #/installation/fiche puis #/installation montrent l'écran « Fiche d'accès » avec l'état vide
                   « Pas de serveur » et son texte, sans le bandeau « Cet écran n'a pas pu s'afficher » et sans aucune
                   erreur en console ni erreur JavaScript pendant ces deux ouvertures.
Le mode serveur (la fiche elle-même) reste vérifié par tests/test_installation_ecrans.py et test_parametres_acces.py.
Jamais donnees/ réel : la démo vit en mémoire, le mode dossier écrit dans l'OPFS du contexte de test.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_installation_fiche.py" -v
"""
import re
import unittest

from commun import (RACINE, CasNavigateur, ServeurStatique, attendre_pret, installer_dossier_simule, preregler_profil,
                    url_fichier)

TITRE_VIDE = "Pas de serveur"
TEXTE_VIDE = "La fiche d'accès décrit le serveur Prévo : elle n'existe qu'en mode serveur."
ROUTES = ("#/installation/fiche", "#/installation")
# Mode dossier servi par un petit serveur de fichiers : au démarrage, Prévo y cherche d'abord un serveur (404 attendus).
ERREURS_SERVEUR_STATIQUE = [re.compile(r"status of 404.*/api/ping"), re.compile(r"status of 404.*/api/csv/")]

ETAT_FICHE_JS = """() => {
  const vide = document.querySelector('#contenu .vide');
  const titre = document.querySelector('#contenu .entete-page h1');
  return {
    ecran: App.ecranCourant && App.ecranCourant.id,
    titre: titre ? titre.textContent.trim() : null,
    videTitre: vide && vide.querySelector('b') ? vide.querySelector('b').textContent.trim() : null,
    videTexte: vide && vide.querySelector('p') ? vide.querySelector('p').textContent.trim() : null,
    videVisible: Boolean(vide && vide.offsetParent !== null),
    bandeauErreur: Boolean(document.querySelector('#contenu .alerte.important')),
  };
}"""


class TestFicheAccesSansServeur(CasNavigateur):

    def ouvrir_les_deux_routes(self, mode):
        """Ouvre #/installation/fiche puis #/installation sur une application prête ; vérifie chaque écran."""
        page = self.page
        self.assertEqual(page.evaluate("App.mode"), mode)
        erreurs_avant = len(self.erreurs_console)
        for route in ROUTES:
            with self.subTest(mode=mode, route=route):
                # L'ancien état vide est marqué : l'écran suivant doit en rendre un nouveau.
                page.evaluate("() => document.querySelectorAll('#contenu .vide').forEach((e) => { e.dataset.ancien = '1'; })")
                page.evaluate("hash => { location.hash = hash; }", route)
                page.wait_for_function("hash => location.hash === hash", arg=route)
                page.wait_for_selector("#contenu .vide:not([data-ancien])", state="visible")
                etat = page.evaluate(ETAT_FICHE_JS)
                self.assertEqual(etat, {"ecran": "installation-fiche", "titre": "Fiche d'accès", "videTitre": TITRE_VIDE,
                                        "videTexte": TEXTE_VIDE, "videVisible": True, "bandeauErreur": False})
                self.assertEqual(page.title(), "Fiche d'accès — Prévo")
        self.assertEqual(self.erreurs_console[erreurs_avant:], [],
                         "aucune erreur console ni JavaScript à l'ouverture de la fiche hors mode serveur")

    def test_demo_pas_de_serveur(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.ouvrir_les_deux_routes("demo")

    def test_mode_dossier_pas_de_serveur(self):
        for motif in ERREURS_SERVEUR_STATIQUE:
            self.autoriser_erreur(motif)
        installer_dossier_simule(self.contexte, "donnees-fiche-acces")
        preregler_profil(self.contexte, "responsable")
        with ServeurStatique(RACINE) as statique:
            page = self.page
            page.goto(statique.url + "/index.html")
            page.click("#btn-dossier")
            page.wait_for_selector("#btn-base-demo", state="visible")
            page.click("#btn-base-demo")
            attendre_pret(page, 30000)
            self.ouvrir_les_deux_routes("dossier")


if __name__ == "__main__":
    unittest.main()
