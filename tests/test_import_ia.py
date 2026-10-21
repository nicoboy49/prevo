"""Proposition des colonnes d'un import par l'IA (tâche T84, ARCHITECTURE.md §18.4, D87 a ; CS91).

Ce qui est vérifié, avec le faux fournisseur (jamais un vrai modèle) :
  - l'IA ne reçoit que les titres des colonnes (au plus 60) et la liste des champs du type : aucune valeur
    de cellule, même si les données de la demande en contiennent ;
  - le schéma demandé ferme les réponses : titre parmi ceux envoyés, champ parmi ceux du type ou « » ;
  - modèle « faux » : la proposition est rendue telle quelle ; « faux-invente » : champ hors liste, titre
    jamais envoyé et champ donné à deux colonnes sont rejetés (listés dans « rejetes »), jamais gardés ;
  - la vérification pure : réponse sans liste refusée, une colonne pour un champ, champ vide ignoré.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_ia.py" -v
"""
import json
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_ia_regles import CasDemoIa, contenu_envoye, regler_ia

SECRET = "valeur-de-cellule-4242"
TITRES = ["Commentaire", "Fabricant", "Code machine", "Emplacement"]

# Données envoyées comme les enverra l'écran d'import, plus un échantillon de cellules qui ne doit pas partir.
DONNEES_JS = """([titres, secret]) => ({
  type: Import.TYPES.equipements.libelle,
  champs: Import.TYPES.equipements.champs.map((c) => ({ cle: c.cle, libelle: c.libelle })),
  colonnes: titres,
  echantillon: [titres.map(() => secret)],
  lignes: [[secret, secret]],
})"""


class TestColonnesImport(CasDemoIa):

    def donnees(self, titres=TITRES):
        return self.page.evaluate(DONNEES_JS, [titres, SECRET])

    def requete_chat(self):
        chats = [r for r in self.faux.requetes if r["chemin"] == "/api/chat"]
        self.assertEqual(len(chats), 1)
        return chats[0]["corps"]

    def test_titres_seulement_et_liste_fermee(self):
        regler_ia(self.contexte, url=self.faux.url)
        self.ouvrir_demo()
        donnees = self.donnees()
        cles = [c["cle"] for c in donnees["champs"]]
        reponse = self.demander("colonnesImport", donnees)
        self.assertTrue(reponse["ok"], reponse)
        self.assertEqual(reponse["resultat"], {"colonnes": [{"entete": t, "champ": c} for t, c in zip(TITRES, cles)],
                                               "rejetes": []})
        corps = self.requete_chat()
        envoye = contenu_envoye(corps)
        self.assertTrue(envoye.startswith("Fonction : colonnesImport"))
        for titre in TITRES:
            self.assertIn(titre, envoye)
        for champ in donnees["champs"]:
            self.assertIn(champ["cle"], envoye)
        texte_complet = json.dumps(corps, ensure_ascii=False)
        self.assertNotIn(SECRET, texte_complet, "aucune valeur de cellule ne part")
        colonnes = corps["format"]["properties"]["colonnes"]["items"]["properties"]
        self.assertEqual(colonnes["entete"]["enum"], TITRES)
        self.assertEqual(colonnes["champ"]["enum"], cles + [""])

    def test_au_plus_soixante_titres(self):
        regler_ia(self.contexte, url=self.faux.url)
        self.ouvrir_demo()
        titres = ["Colonne %d" % n for n in range(1, 71)]
        reponse = self.demander("colonnesImport", self.donnees(titres))
        self.assertTrue(reponse["ok"], reponse)
        envoye = contenu_envoye(self.requete_chat())
        self.assertIn("- Colonne 60\n", envoye + "\n")
        self.assertNotIn("Colonne 61", envoye)

    def test_proposition_inventee_rejetee(self):
        regler_ia(self.contexte, url=self.faux.url, modele="faux-invente")
        self.ouvrir_demo()
        donnees = self.donnees()
        premier = donnees["champs"][0]["cle"]
        reponse = self.demander("colonnesImport", donnees)
        self.assertTrue(reponse["ok"], reponse)
        self.assertEqual(reponse["resultat"]["colonnes"], [{"entete": TITRES[0], "champ": premier}])
        self.assertEqual(reponse["resultat"]["rejetes"], [
            {"entete": TITRES[-1], "champ": "champ_invente"},
            {"entete": "Colonne jamais envoyée", "champ": donnees["champs"][-1]["cle"]},
            {"entete": TITRES[-1], "champ": premier},
        ])


class TestVerificationPure(CasNavigateur):
    """Ia.PROMPTS.colonnesImport.verifier, sans fournisseur."""

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def verifier(self, objet):
        return self.page.evaluate("""(objet) => {
          const d = { colonnes: ['A', 'B', 'C'], champs: [{ cle: 'repere' }, { cle: 'designation' }] };
          try { return Ia.PROMPTS.colonnesImport.verifier(objet, d); } catch (e) { return { erreur: e.name + ' ' + e.message }; }
        }""", objet)

    def test_reponses_bancales(self):
        self.assertIn("IaReponseInvalide", self.verifier({"autre": []})["erreur"])
        self.assertIn("IaReponseInvalide", self.verifier(None)["erreur"])
        resultat = self.verifier({"colonnes": [
            {"entete": "A", "champ": "repere"},
            {"entete": "A", "champ": "designation"},        # même colonne une seconde fois
            {"entete": "B", "champ": ""},                    # rien proposé
            {"entete": "C", "champ": "repere"},              # champ déjà pris
            {"entete": "C", "champ": "designation"},
            "pas un objet",
        ]})
        self.assertEqual(resultat["colonnes"], [{"entete": "A", "champ": "repere"}, {"entete": "C", "champ": "designation"}])
        self.assertEqual(resultat["rejetes"], [{"entete": "A", "champ": "designation"}, {"entete": "C", "champ": "repere"}])


if __name__ == "__main__":
    unittest.main()
