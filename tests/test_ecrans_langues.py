"""Chantier multilingue, Lot 5 — tous les écrans s'ouvrent en turc, italien et portugais (critères CS160 et CS161 ; T375).

Refait le parcours de la photographie des écrans (outils/photographier_ecrans.py : mêmes écrans, onglets, fenêtres,
formulaires envoyés vides, coque, démarrage, choix du profil, connexion, porte, assistant d'installation ; démo en
file:// et serveur.py ; trois profils ; horloges figées) dans chacune des trois langues du Lot 5, la langue posée dans
localStorage « prevo.langue » avant chaque chargement, comme le fait le sélecteur. Le relevé est celui de
test_ecrans_anglais.py (ReleveurAnglais) avec la langue en paramètre. Pour chaque écran :
    - aucune erreur JavaScript (pageerror) ni message d'erreur dans la console (sauf les réponses refusées voulues
      par le serveur, déjà permises en français et en anglais : EXCEPTIONS de test_ecrans_anglais) ;
    - aucun avertissement du moteur pour une clé absente : toutes les clés de l'interface sont traduites ; les clés
      de l'aide longue (aide.*) se replient sur l'anglais sans avertissement (D158) ;
    - document.documentElement.lang vaut le code de la langue ;
    - même liste d'écrans que le relevé français (aucun écran perdu).
Et, pour chaque langue, la mention « traduction automatique — corrections bienvenues » au pied du menu (CS161).
La recherche de texte français resté en dur (texte qui ne passe pas par les dictionnaires) est faite par
test_ecrans_anglais.py sur les mêmes écrans : elle ne dépend pas de la langue choisie.

Lancer depuis la racine du projet (au travers du verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_ecrans_langues.py" -v
Durée : environ quinze minutes (trois langues, deux modes, Chromium headless).
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path

import test_ecrans_anglais as anglais
from test_ecrans_anglais import Probleme, exception_de, photo, rapport, sync_playwright

LANGUES = ("tr", "it", "pt-PT")
LIGNES_MONTREES = 80


class ReleveurLangue(anglais.ReleveurAnglais):
    """Le releveur du test anglais, pour une autre langue (le code remplace LANGUE dans le contrôle de lang)."""

    def __init__(self, playwright, navigateur, mode, langue):
        photo.Releveur.__init__(self, playwright, navigateur, mode, langue=langue)
        self.code = langue
        self.problemes = []
        self.courant = ("aucun", "début du relevé")
        self.mentions = []

    def noter(self, page, profil, nom, zones, vide_permis=False):
        self.courant = (profil, nom)
        entree = photo.Releveur.noter(self, page, profil, nom, zones, vide_permis)
        if entree is not None:
            lang = page.evaluate("document.documentElement.lang")
            if lang != self.code:
                self.signaler("lang", "<html lang=%r> (attendu %r)" % (lang, self.code))
            mention = page.evaluate("(document.querySelector('#menu-traduction') || {}).textContent || ''")
            if mention.strip():
                self.mentions.append(mention.strip())
        return entree


class TestEcransLangues(unittest.TestCase):
    """Un test par langue et par mode."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise unittest.SkipTest("Playwright pour Python n'est pas installé")
        cls._playwright = sync_playwright().start()
        cls.addClassCleanup(cls._playwright.stop)
        cls.navigateur = cls._playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.navigateur.close)

    def verifier(self, langue, mode):
        francais = photo.lire_reference(mode)
        debut = time.monotonic()
        releveur = ReleveurLangue(self._playwright, self.navigateur, mode, langue)
        try:
            releve = releveur.relever()
        except photo.ErreurReleve as erreur:
            releve = photo.document(mode, releveur.ecrans)
            releveur.problemes.append(Probleme(mode, "?", releveur.dernier, "relevé interrompu", str(erreur)))
        duree = time.monotonic() - debut
        problemes = list(releveur.problemes)
        attendus = {(e["profil"], e["ecran"]) for e in francais["ecrans"]}
        obtenus = {(e["profil"], e["ecran"]) for e in releve["ecrans"]}
        for profil, ecran in sorted(attendus - obtenus):
            problemes.append(Probleme(mode, profil, ecran, "écran absent", "relevé en français, pas en %s" % langue))
        for profil, ecran in sorted(obtenus - attendus):
            problemes.append(Probleme(mode, profil, ecran, "écran en plus", "absent du relevé français"))
        retenus = [p for p in problemes if exception_de(p) is None]
        dossier = Path(tempfile.gettempdir()) / "prevo-ecrans-langues"
        dossier.mkdir(parents=True, exist_ok=True)
        lignes = rapport(retenus)
        (dossier / ("rapport-%s-%s.txt" % (langue, mode))).write_text("\n".join(lignes) + "\n", encoding="utf-8")
        if retenus:
            montrees = lignes[:LIGNES_MONTREES] + (["… et %d autres" % (len(lignes) - LIGNES_MONTREES)]
                                                   if len(lignes) > LIGNES_MONTREES else [])
            self.fail("%d problème(s) en %s, mode %s (%d écrans en %.0f s) :\n  %s" % (
                len(lignes), langue, mode, len(releve["ecrans"]), duree, "\n  ".join(montrees)))
        self.assertTrue(releveur.mentions, "mention « traduction automatique » jamais vue au pied du menu (%s)" % langue)
        sys.stderr.write("\n  [%s, %s] %d écrans sans problème en %.0f s " % (langue, mode, len(releve["ecrans"]), duree))

    def test_turc_demo(self):
        self.verifier("tr", "demo")

    def test_turc_serveur(self):
        self.verifier("tr", "serveur")

    def test_italien_demo(self):
        self.verifier("it", "demo")

    def test_italien_serveur(self):
        self.verifier("it", "serveur")

    def test_portugais_demo(self):
        self.verifier("pt-PT", "demo")

    def test_portugais_serveur(self):
        self.verifier("pt-PT", "serveur")


if __name__ == "__main__":
    unittest.main()
