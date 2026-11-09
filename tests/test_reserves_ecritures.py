"""Tests des écritures des réserves des contrôles, 2.2 (controles-reserves.js et controles-ecritures.js, T413 ;
CS170, CS176, D18, D156, D187).

Par l'API (Controles.*) dans l'application ouverte, sans passer par les fenêtres (T418-T420) :
    serveur  : serveur.py sur une copie temporaire du jeu de démo, profil responsable ; CSV relus sur le disque.
               Un contrôle créé par le test (aucun identifiant de contrôle écrit en dur) réalisé avec trois réserves
               les garde en trois lignes (puces retirées, même date, même échéance, levee 0) ; un second envoi
               identique ne crée rien (fichiers identiques à l'octet) ; en lever une laisse les deux autres ouvertes ;
               une nouvelle réalisation n'en efface ni n'en modifie aucune (« observations » lu comme synonyme) ;
               depuis T418, observations et observations_levees ne sont plus écrites et le journal de la
               réalisation dit « 3 réserves » ; marqueurs du journal (D156). Refus sans rien écrire : contrôle ou réserve introuvable, dates (absente, illisible, future,
               avant le contrôle), texte sans réserve, gravité inconnue, levée d'une réserve levée, commentaire vide,
               OT introuvable ou d'un autre équipement, correction d'une réserve levée, second OT relié ;
    demo     : index.html en file://, écran en anglais (prevo.langue = en) : un 2e et un 3e rapport du même contrôle et
               du même jour prennent « -2 », « -3 » (le stockage refuse le nom pris par un message dans la langue de
               l'écran ; avant T413, seul le message français était reconnu) ; refus des réserves en anglais.
Dates calculées depuis la date du jour de l'application (Donnees.aujourdhui()).

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_reserves_ecritures.py" -v
"""
import csv
import datetime
import io
import json
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

PDF = b"%PDF-1.4\n% rapport de test (T413)\n%%EOF\n"
ENTETE_RESERVES = b"id;controle_id;date_controle;texte;gravite;echeance_levee;levee;date_levee;commentaire_levee;ot_id"
SAISIE_TROIS = "- Différentiel 30 mA à remplacer\r\n\r\n• Schéma unifilaire à mettre à jour\n1. Prise de terre à reprendre  "
TEXTES_TROIS = ["Différentiel 30 mA à remplacer", "Schéma unifilaire à mettre à jour", "Prise de terre à reprendre"]

# Appel d'une fonction de Controles ; `fichier` (facultatif) devient un File ajouté en dernier argument.
APPEL_JS = """async ([fonction, arguments_, fichier]) => {
  const args = arguments_.slice();
  if (fichier) args.push(new File([new Uint8Array(fichier.octets)], fichier.nom, { type: fichier.type || '' }));
  try { return 'accepté:' + JSON.stringify(await Controles[fonction](...args)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items()}


def reserves_de(dossier, controle_id):
    return [propre(r) for r in lire_csv(dossier, "reserves_controle.csv") if brut(r["controle_id"]) == controle_id]


def controle_de(dossier, controle_id):
    return next(propre(c) for c in lire_csv(dossier, "controles_reglementaires.csv") if c["id"] == controle_id)


def journal(dossier, table, ids):
    return [e["action"] for e in lire_csv(dossier, "journal.csv") if e["table"] == table and e["id_ligne"] in ids]


def fr(date):
    return date.strftime("%d/%m/%Y")


class CasReserves(CasNavigateur):

    def appeler(self, fonction, *arguments, fichier=None):
        return self.page.evaluate(APPEL_JS, [fonction, list(arguments), fichier])

    def accepte(self, fonction, *arguments, fichier=None):
        resultat = self.appeler(fonction, *arguments, fichier=fichier)
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def refuse(self, attendu, fonction, *arguments):
        resultat = self.appeler(fonction, *arguments)
        self.assertTrue(resultat.startswith("refus:") and attendu in resultat, resultat)

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))


# ---------------------------------------------------------------------------
# Serveur : CSV relus sur le disque
# ---------------------------------------------------------------------------

class TestServeur(CasReserves):

    def ouvrir(self, serveur):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/#/controles")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def equipement_avec_ot(self, dossier):
        """(équipement qui a au moins un OT, un de ses OT, un OT d'un autre équipement), lus dans le jeu copié."""
        ots = [propre(o) for o in lire_csv(dossier, "ordres_travail.csv") if brut(o["equipement_id"])]
        equipements = {e["id"] for e in lire_csv(dossier, "equipements.csv")}
        ot = next(o for o in ots if o["equipement_id"] in equipements)
        autre = next(o for o in ots if o["equipement_id"] != ot["equipement_id"])
        return ot["equipement_id"], ot["id"], autre["id"]

    def nouveau_controle(self, equipement_id, nature):
        return self.accepte("creerControle", {"equipement_id": equipement_id, "nature": nature, "periodicite_mois": "12"})

    def test_trois_reserves_levee_et_nouvelle_realisation_n_efface_rien(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            dossier = serveur.dossier
            chemin_reserves = dossier / "reserves_controle.csv"
            chemin_controles = dossier / "controles_reglementaires.csv"
            equipement, _, _ = self.equipement_avec_ot(dossier)
            controle = self.nouveau_controle(equipement, "Installations électriques (T413)")
            jour = self.aujourdhui()
            d1, d2, d3 = (jour - datetime.timedelta(days=n) for n in (300, 100, 10))
            echeance = d1 + datetime.timedelta(days=20)

            # Contrôle réalisé avec trois réserves : trois lignes, puces et blancs retirés, ouvertes
            rendu = self.accepte("enregistrerRealisation", controle, {
                "date": d1.isoformat(), "organisme": "Organisme T413", "reserves": SAISIE_TROIS,
                "echeance_levee": echeance.isoformat()})
            self.assertEqual(rendu["derniere_date"], d1.isoformat())
            self.assertEqual(len(rendu["reserves"]), 3)
            self.assertTrue(all(i.startswith("RES-") and len(i) == 9 for i in rendu["reserves"]), rendu)
            reserves = reserves_de(dossier, controle)
            self.assertEqual([r["id"] for r in reserves], rendu["reserves"])
            self.assertEqual([r["texte"] for r in reserves], TEXTES_TROIS)
            for r in reserves:
                self.assertEqual((r["date_controle"], r["echeance_levee"], r["levee"], r["date_levee"],
                                  r["commentaire_levee"], r["ot_id"], r["gravite"]),
                                 (d1.isoformat(), echeance.isoformat(), "0", "", "", "", ""))
            self.assertTrue(chemin_reserves.read_bytes().lstrip(b"\xef\xbb\xbf").startswith(ENTETE_RESERVES))
            # Depuis T418 : observations et observations_levees ne sont plus écrites (valeurs de la création)
            ligne = controle_de(dossier, controle)
            self.assertEqual((ligne["derniere_date"], ligne["organisme"], ligne["observations"], ligne["observations_levees"]),
                             (d1.isoformat(), "Organisme T413", "", "1"))
            # Journal (D156) : une entrée par réserve créée ; celle du contrôle dit le nombre de réserves
            actions = journal(dossier, "reserves_controle", rendu["reserves"])
            self.assertEqual(len(actions), 3, actions)
            self.assertTrue(all(a == "création — réserves relevées au contrôle du %s : 3" % fr(d1) for a in actions), actions)
            realisation = [a for a in journal(dossier, "controles_reglementaires", [controle]) if "contrôle réalisé" in a]
            self.assertEqual(len(realisation), 1, realisation)
            self.assertTrue(realisation[0].endswith(" — contrôle réalisé le %s par Organisme T413 ; sans rapport joint ; "
                                                    "3 réserves" % fr(d1)), realisation)
            self.assertNotIn("observations", realisation[0])

            # Second envoi identique (essai après un échec, double clic) : rien de recréé, fichiers identiques
            octets = (chemin_reserves.read_bytes(), chemin_controles.read_bytes())
            rendu = self.accepte("enregistrerRealisation", controle, {
                "date": d1.isoformat(), "organisme": "Organisme T413", "reserves": SAISIE_TROIS,
                "echeance_levee": echeance.isoformat()})
            self.assertEqual(rendu["reserves"], [])
            self.assertEqual(self.accepte("ajouterReserves", controle, {
                "date_controle": d1.isoformat(), "texte": "\n".join(TEXTES_TROIS)}), [])
            self.assertEqual((chemin_reserves.read_bytes(), chemin_controles.read_bytes()), octets)
            self.assertEqual(len(journal(dossier, "reserves_controle", [r["id"] for r in reserves])), 3)

            # En lever une : les deux autres restent ouvertes
            premiere, deuxieme, troisieme = (r["id"] for r in reserves)
            levee_le = d1 + datetime.timedelta(days=5)
            self.assertIs(self.accepte("leverReserve", premiere, {
                "date": levee_le.isoformat(), "commentaire": "Différentiel remplacé, essai de déclenchement fait"}), True)
            apres = {r["id"]: r for r in reserves_de(dossier, controle)}
            self.assertEqual((apres[premiere]["levee"], apres[premiere]["date_levee"], apres[premiere]["commentaire_levee"]),
                             ("1", levee_le.isoformat(), "Différentiel remplacé, essai de déclenchement fait"))
            self.assertEqual([apres[i]["levee"] for i in (deuxieme, troisieme)], ["0", "0"])
            self.assertEqual({i: apres[i] for i in (deuxieme, troisieme)}, {r["id"]: r for r in reserves[1:]})
            self.assertIn("modification : levee, date_levee, commentaire_levee — réserve levée le %s : "
                          "Différentiel remplacé, essai de déclenchement fait" % fr(levee_le),
                          journal(dossier, "reserves_controle", [premiere]))

            # Nouvelle réalisation avec une réserve : ajoutée, aucune des trois n'est effacée ni modifiée
            avant = reserves_de(dossier, controle)
            rendu = self.accepte("enregistrerRealisation", controle, {"date": d2.isoformat(),
                                                                     "reserves": "Éclairage de secours absent"})
            self.assertEqual(len(rendu["reserves"]), 1)
            apres = reserves_de(dossier, controle)
            self.assertEqual(apres[:3], avant)
            self.assertEqual((apres[3]["texte"], apres[3]["date_controle"], apres[3]["echeance_levee"], apres[3]["levee"]),
                             ("Éclairage de secours absent", d2.isoformat(), "", "0"))
            # « observations » (ancienne fenêtre, jusqu'à T418) : synonyme de « reserves »
            rendu = self.accepte("enregistrerRealisation", controle, {"date": d3.isoformat(),
                                                                     "observations": "Garde-corps à refixer"})
            apres = reserves_de(dossier, controle)
            self.assertEqual(len(apres), 5)
            self.assertEqual((apres[4]["id"], apres[4]["texte"], apres[4]["date_controle"]),
                             (rendu["reserves"][0], "Garde-corps à refixer", d3.isoformat()))
            # Réalisation sans réserve : rien n'est ajouté ni changé dans les réserves ; journal « sans réserve »
            octets = chemin_reserves.read_bytes()
            rendu = self.accepte("enregistrerRealisation", controle, {"date": jour.isoformat()})
            self.assertEqual(rendu["reserves"], [])
            self.assertEqual(chemin_reserves.read_bytes(), octets)
            ligne = controle_de(dossier, controle)
            self.assertEqual((ligne["derniere_date"], ligne["observations"], ligne["observations_levees"]),
                             (jour.isoformat(), "", "1"))
            self.assertTrue(journal(dossier, "controles_reglementaires", [controle])[-1].endswith(
                "contrôle réalisé le %s ; sans rapport joint ; sans réserve" % fr(jour)))
            self.assertEqual([r["levee"] for r in reserves_de(dossier, controle)], ["1", "0", "0", "0", "0"])
            # Doublons exacts d'une même saisie gardés (le rapport peut les répéter), une seule fois même rejoués
            doubles = self.accepte("ajouterReserves", controle, {"date_controle": d3.isoformat(),
                                                                 "texte": "Garde-corps à refixer\nGarde-corps à refixer"})
            self.assertEqual(len(doubles), 1)
            self.assertEqual(self.accepte("ajouterReserves", controle, {"date_controle": d3.isoformat(),
                                                                        "texte": "Garde-corps à refixer\nGarde-corps à refixer"}), [])
            self.assertEqual(len(reserves_de(dossier, controle)), 6)

    def test_refus_correction_et_lien_avec_un_ot(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            dossier = serveur.dossier
            chemin_reserves = dossier / "reserves_controle.csv"
            chemin_controles = dossier / "controles_reglementaires.csv"
            equipement, ot, ot_autre = self.equipement_avec_ot(dossier)
            controle = self.nouveau_controle(equipement, "VGP du pont roulant (T413)")
            jour = self.aujourdhui()
            d1 = jour - datetime.timedelta(days=60)
            avant_d1 = (d1 - datetime.timedelta(days=1)).isoformat()
            demain = (jour + datetime.timedelta(days=1)).isoformat()
            ouvertes = self.accepte("ajouterReserves", controle, {
                "date_controle": d1.isoformat(), "texte": "Crochet usé\nLimiteur de charge à régler\nPlaque de charge illisible",
                "gravite": "Majeure"})
            self.assertEqual([r["gravite"] for r in reserves_de(dossier, controle)], ["majeure"] * 3)
            reserve, autre, troisieme = ouvertes

            def fichiers():
                return chemin_reserves.read_bytes(), chemin_controles.read_bytes()

            octets = fichiers()
            # Ajout : contrôle introuvable, dates, texte sans réserve, gravité, échéance
            self.refuse("CTR-9999 est introuvable", "ajouterReserves", "CTR-9999", {"date_controle": d1.isoformat(), "texte": "x"})
            for valeurs, attendu in (
                    ({"texte": "Crochet usé"}, "Indiquez la date du contrôle"),
                    ({"date_controle": "2026-13-01", "texte": "Crochet usé"}, "date illisible"),
                    ({"date_controle": "12/11/2025", "texte": "Crochet usé"}, "date illisible"),
                    ({"date_controle": demain, "texte": "Crochet usé"}, "futur"),
                    ({"date_controle": d1.isoformat(), "texte": " - \n • \n"}, "au moins une réserve"),
                    ({"date_controle": d1.isoformat(), "texte": "Crochet usé", "gravite": "grave"}, "Gravité inconnue (grave)"),
                    ({"date_controle": d1.isoformat(), "texte": "Crochet usé", "echeance_levee": avant_d1}, "ne peut pas précéder"),
                    ({"date_controle": d1.isoformat(), "texte": "Crochet usé", "echeance_levee": "2026-02-30"}, "date illisible")):
                with self.subTest(ajout=valeurs):
                    self.refuse(attendu, "ajouterReserves", controle, valeurs)
            # Réalisation dont l'échéance précède la date : refusée AVANT d'écrire le contrôle (D18)
            self.refuse("ne peut pas précéder", "enregistrerRealisation", controle, {
                "date": d1.isoformat(), "reserves": "Crochet usé", "echeance_levee": avant_d1})
            self.assertEqual(fichiers(), octets)

            # Levée : introuvable, date absente, future, avant le contrôle, commentaire vide, OT introuvable ou autre
            self.refuse("RES-99999 est introuvable", "leverReserve", "RES-99999", {"date": d1.isoformat(), "commentaire": "x"})
            for valeurs, attendu in (
                    ({"commentaire": "Crochet changé"}, "Indiquez la date de levée"),
                    ({"date": demain, "commentaire": "Crochet changé"}, "futur"),
                    ({"date": avant_d1, "commentaire": "Crochet changé"}, "une levée antérieure est refusée"),
                    ({"date": d1.isoformat(), "commentaire": "  "}, "Décrivez ce qui a été fait"),
                    ({"date": d1.isoformat(), "commentaire": "Crochet changé", "ot_id": "OT-1999-9999"}, "OT-1999-9999 est introuvable"),
                    ({"date": d1.isoformat(), "commentaire": "Crochet changé", "ot_id": ot_autre}, "autre équipement")):
                with self.subTest(levee=valeurs):
                    self.refuse(attendu, "leverReserve", reserve, valeurs)
            # Lien avec un OT : introuvable, autre équipement, sans OT
            self.refuse("introuvable", "lierOtAReserve", reserve, "OT-1999-9999")
            self.refuse("autre équipement", "lierOtAReserve", reserve, ot_autre)
            self.refuse("Choisissez l'OT", "lierOtAReserve", reserve, "")
            # Correction : texte vide, gravité, échéance avant le contrôle
            self.refuse("texte de la réserve est obligatoire", "modifierReserve", reserve, {"texte": "  "})
            self.refuse("Gravité inconnue", "modifierReserve", reserve, {"gravite": "énorme"})
            self.refuse("ne peut pas précéder", "modifierReserve", reserve, {"echeance_levee": avant_d1})
            self.assertEqual(fichiers(), octets)

            # Correction acceptée : champs changés rendus, journal « correction de la réserve »
            echeance = (d1 + datetime.timedelta(days=45)).isoformat()
            changes = self.accepte("modifierReserve", reserve, {"texte": " Crochet du palan usé ", "gravite": "CRITIQUE",
                                                                 "echeance_levee": echeance})
            self.assertEqual(sorted(changes), ["echeance_levee", "gravite", "texte"])
            ligne = next(r for r in reserves_de(dossier, controle) if r["id"] == reserve)
            self.assertEqual((ligne["texte"], ligne["gravite"], ligne["echeance_levee"], ligne["levee"]),
                             ("Crochet du palan usé", "critique", echeance, "0"))
            self.assertIn("modification : texte, gravite, echeance_levee — correction de la réserve",
                          journal(dossier, "reserves_controle", [reserve]))
            self.assertEqual(self.accepte("modifierReserve", reserve, {"echeance_levee": "", "gravite": ""}),
                             ["gravite", "echeance_levee"])

            # Lien : une seule fois ; le même OT redonné est accepté sans rien écrire ; un autre est refusé
            self.assertIs(self.accepte("lierOtAReserve", reserve, ot), True)
            self.assertEqual(next(r for r in reserves_de(dossier, controle) if r["id"] == reserve)["ot_id"], ot)
            self.assertIn("modification : ot_id — reliée à %s" % ot, journal(dossier, "reserves_controle", [reserve]))
            octets = fichiers()
            self.assertIs(self.accepte("lierOtAReserve", reserve, ot), True)
            self.refuse("déjà reliée à %s" % ot, "lierOtAReserve", reserve, ot_autre)
            self.assertEqual(fichiers(), octets)

            # Levée avec l'OT de l'équipement ; une levée sans OT garde l'OT déjà lié
            self.accepte("leverReserve", autre, {"date": jour.isoformat(), "commentaire": "Limiteur réglé", "ot_id": ot})
            self.accepte("leverReserve", reserve, {"date": d1.isoformat(), "commentaire": "Crochet remplacé"})
            lignes = {r["id"]: r for r in reserves_de(dossier, controle)}
            self.assertEqual((lignes[autre]["levee"], lignes[autre]["ot_id"], lignes[autre]["date_levee"]),
                             ("1", ot, jour.isoformat()))
            self.assertEqual((lignes[reserve]["levee"], lignes[reserve]["ot_id"]), ("1", ot))
            self.assertEqual(lignes[troisieme]["levee"], "0")

            # Une réserve levée est un fait : ni relevée, ni corrigée, ni reliée
            octets = fichiers()
            self.refuse("déjà levée", "leverReserve", reserve, {"date": jour.isoformat(), "commentaire": "encore"})
            self.refuse("elle ne se modifie plus", "modifierReserve", autre, {"texte": "Autre texte"})
            self.accepte("lierOtAReserve", autre, ot)               # même OT : rien à écrire
            self.refuse("aucun OT ne peut plus lui être relié", "lierOtAReserve", reserve, "OT-1999-0001")
            self.assertEqual(fichiers(), octets)


# ---------------------------------------------------------------------------
# Démo en anglais : rapport du même jour numéroté, refus dans la langue de l'écran
# ---------------------------------------------------------------------------

class TestDemoAnglais(CasReserves):

    def test_deuxieme_rapport_du_meme_jour_prend_2_en_anglais(self):
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        preregler_profil(self.contexte, "responsable")
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("I18n.langue"), "en")
        controle = scenarios_demo()["controle_a_jour"]
        fichier = {"nom": "report.pdf", "type": "application/pdf", "octets": list(PDF)}
        noms = [self.accepte("ecrireRapport", controle, "2026-10-20", fichier=fichier) for _ in range(3)]
        base = "controle-%s-2026-10-20" % controle
        self.assertEqual(noms, [base + ".pdf", base + "-2.pdf", base + "-3.pdf"])
        # Une autre erreur du stockage n'est pas prise pour un nom déjà pris : elle remonte telle quelle
        resultat = self.page.evaluate("""async () => {
          const ecrire = App.adaptateur.ecrireDocument;
          let essais = 0;
          App.adaptateur.ecrireDocument = async () => { essais += 1; throw new Donnees.ErreurStockage('Disk full.'); };
          try { await Controles.ecrireRapport('CTR-0001', '2026-10-21', new File([new Uint8Array([37, 80, 68, 70])], 'r.pdf')); return 'accepté'; }
          catch (erreur) { return erreur.message + ' / ' + essais; }
          finally { App.adaptateur.ecrireDocument = ecrire; }
        }""")
        self.assertEqual(resultat, "Disk full. / 1")
        # Refus des écritures des réserves dans la langue de l'écran
        self.refuse("Enter at least one finding", "ajouterReserves", controle,
                    {"date_controle": self.aujourdhui().isoformat(), "texte": ""})
        self.refuse("Finding RES-99999 not found.", "leverReserve", "RES-99999", {"date": "2026-01-01", "commentaire": "x"})


if __name__ == "__main__":
    unittest.main()
