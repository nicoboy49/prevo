"""Tests des écritures des habilitations, 2.2 (equipe-ecritures.js, T431 ; CS172, CS176, CS179).

Par l'API (Equipe.*) dans l'application ouverte, sans passer par les fenêtres (T432) :
    serveur  : serveur.py sur une copie temporaire du jeu de démo, profil responsable ; CSV et documents relus sur
               le disque. Échéance calculée (obtention 15/01/2024 + 36 mois = 15/01/2027) ou gardée si saisie ;
               recyclage ramené à l'entier ; type du catalogue et nature inconnus ramenés à vide ; justificatif écrit
               dans documents/ et nommé sur la ligne ; correction (échéance vidée → recalculée) ; renouvellement
               (intitulé, recyclage, type et nature repris, échéance depuis la nouvelle obtention, justificatif
               nouveau facultatif, ancienne ligne intacte) ; refus sans rien écrire (recyclage, type ou taille du
               fichier) ; profil technicien : rien d'écrit (D195, côté application) ;
    demo     : index.html en file://, « Essayer avec les données de démo » (aucun horodatage devant les noms) : nom
               « habilitation-<technicien>-<intitulé>-<date>.pdf », « -2 », « -3 » si pris, accents retirés, photo
               réduite à 2 400 px en JPEG ; documents relus par App.adaptateur.lireDocument.
Les techniciens sont créés par le test (aucun identifiant du jeu de démo écrit en dur) ; dates fixes.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations_ecritures.py" -v
"""
import csv
import io
import json
import re
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

PDF = b"%PDF-1.4\n% justificatif de test (T431)\n%%EOF\n"
NEUF_MO = 9 * 1024 * 1024

# Appel d'une fonction d'Equipe ; `fichier` (facultatif) devient un File ajouté en dernier argument :
# { nom, type, octets } ou { nom, type, taille } (zéros, en-tête PDF) ou { nom, image: [largeur, hauteur] } (PNG).
APPEL_JS = """async ([fonction, arguments_, fichier]) => {
  const args = arguments_.slice();
  if (fichier) {
    let contenu;
    if (fichier.image) {
      const toile = document.createElement('canvas');
      [toile.width, toile.height] = fichier.image;
      const dessin = toile.getContext('2d');
      dessin.fillStyle = '#c0392b'; dessin.fillRect(0, 0, toile.width, toile.height);
      contenu = await new Promise((rendre) => toile.toBlob(rendre, 'image/png'));
    } else if (fichier.taille) {
      contenu = new Uint8Array(fichier.taille);
      contenu.set(new TextEncoder().encode('%PDF-1.4'));
    } else {
      contenu = new Uint8Array(fichier.octets);
    }
    args.push(new File([contenu], fichier.nom, { type: fichier.type || '' }));
  }
  try { return 'accepté:' + JSON.stringify(await Equipe[fonction](...args)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""

# Document relu par l'adaptateur (mode démo) : { octets, debut, largeur, hauteur } (dimensions pour une image).
LIRE_DOCUMENT_JS = """async (nom) => {
  const blob = await App.adaptateur.lireDocument(nom);
  if (!blob) return null;
  const octets = Array.from(new Uint8Array(await blob.arrayBuffer()));
  const resultat = { taille: octets.length, debut: octets.slice(0, 3) };
  if (octets[0] === 0xFF && octets[1] === 0xD8) {
    const image = await createImageBitmap(blob);
    Object.assign(resultat, { largeur: image.width, hauteur: image.height });
  } else {
    resultat.octets = octets;
  }
  return resultat;
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def ligne_de(dossier, habilitation_id):
    return next(h for h in lire_csv(dossier, "habilitations.csv") if h["id"] == habilitation_id)


def valeurs(ligne, *champs):
    return tuple(brut(ligne[champ]) for champ in champs)


def fichier_pdf(nom="titre.pdf"):
    return {"nom": nom, "type": "application/pdf", "octets": list(PDF)}


class CasEcritures(CasNavigateur):

    def ouvrir_serveur(self, serveur, profil="responsable", technicien_id="", page=None):
        page = page or self.page
        preregler_profil(page.context, profil, technicien_id=technicien_id)
        page.goto(serveur.url + "/#/equipe")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")

    def appeler(self, fonction, *arguments, fichier=None, page=None):
        return (page or self.page).evaluate(APPEL_JS, [fonction, list(arguments), fichier])

    def accepte(self, fonction, *arguments, fichier=None, page=None):
        resultat = self.appeler(fonction, *arguments, fichier=fichier, page=page)
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def refuse(self, attendu, fonction, *arguments, fichier=None, page=None):
        resultat = self.appeler(fonction, *arguments, fichier=fichier, page=page)
        self.assertTrue(resultat.startswith("refus:") and attendu in resultat, resultat)

    def nouveau_technicien(self, nom):
        return self.accepte("creerTechnicien", {"nom": nom, "prenom": "Essai"})


# ---------------------------------------------------------------------------
# Serveur : CSV et documents relus sur le disque
# ---------------------------------------------------------------------------

class TestServeur(CasEcritures):

    def test_echeance_calculee_ou_gardee_et_justificatif_ecrit_et_nomme(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            tec = self.nouveau_technicien("Recyclage")
            documents = serveur.dossier / "documents"

            # Justificatif : écrit dans documents/, nom rendu (horodatage du serveur devant le nom demandé)
            nom = self.accepte("ecrireJustificatif", tec, "BR", "2024-01-15", fichier=fichier_pdf())
            self.assertRegex(nom, r"^\d{8}-\d{6}-habilitation-%s-BR-2024-01-15\.pdf$" % tec)
            self.assertEqual((documents / nom).read_bytes(), PDF)

            # CS172 : obtenue le 15/01/2024, 36 mois, sans échéance saisie → échéance 2027-01-15
            br = self.accepte("ajouterHabilitation", tec, {
                "intitule": "BR", "date_obtention": "2024-01-15", "recyclage_mois": "36", "catalogue_id": "h02",
                "nature_source": "recommandation", "justificatif": nom})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, br), "technicien_id", "intitule", "date_obtention",
                                     "date_echeance", "recyclage_mois", "justificatif", "catalogue_id", "nature_source"),
                             (tec, "BR", "2024-01-15", "2027-01-15", "36", nom, "H02", "recommandation"))
            # Échéance saisie (date écrite sur le titre) : gardée telle quelle
            caces = self.accepte("ajouterHabilitation", tec, {
                "intitule": "CACES R489", "date_obtention": "2024-01-15", "date_echeance": "2028-06-30",
                "recyclage_mois": "60", "catalogue_id": "H12", "nature_source": "obligation"})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces), "date_echeance", "recyclage_mois", "justificatif"),
                             ("2028-06-30", "60", ""))
            # Recyclage « 036 » → 36 ; type du catalogue et nature inconnus → vides
            h0v = self.accepte("ajouterHabilitation", tec, {
                "intitule": "H0V", "date_obtention": "2024-01-15", "recyclage_mois": "036", "catalogue_id": "H99",
                "nature_source": "inventée"})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, h0v), "date_echeance", "recyclage_mois", "catalogue_id",
                                     "nature_source"), ("2027-01-15", "36", "", ""))
            # Sans recyclage ni échéance : habilitation sans échéance (règle d'avant la 2.2)
            libre = self.accepte("ajouterHabilitation", tec, {"intitule": "Permis de feu", "date_obtention": "2024-01-15"})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, libre), "date_echeance", "recyclage_mois", "catalogue_id"),
                             ("", "", ""))
            # Colonnes du format 4 dans le fichier
            entete = (serveur.dossier / "habilitations.csv").read_bytes().split(b"\r\n")[0]
            self.assertTrue(entete.endswith(b";recyclage_mois;justificatif;catalogue_id;nature_source"), entete)

    def test_correction_et_renouvellement_reprennent_le_type_et_recalculent_l_echeance(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            tec = self.nouveau_technicien("Renouvellement")
            documents = serveur.dossier / "documents"
            ancien = self.accepte("ecrireJustificatif", tec, "BR", "2024-01-15", fichier=fichier_pdf())
            br = self.accepte("ajouterHabilitation", tec, {
                "intitule": "BR", "date_obtention": "2024-01-15", "recyclage_mois": "36", "catalogue_id": "H02",
                "nature_source": "recommandation", "justificatif": ancien})
            avant = ligne_de(serveur.dossier, br)

            # Renouvellement avec un justificatif nouveau : intitulé, recyclage, type, nature repris ;
            # échéance = nouvelle obtention + 36 mois ; l'ancienne ligne reste telle quelle
            nouveau = self.accepte("ecrireJustificatif", tec, "BR", "2026-11-02", fichier=fichier_pdf("scan.PDF"))
            self.assertRegex(nouveau, r"-habilitation-%s-BR-2026-11-02\.pdf$" % tec)
            self.assertEqual((documents / nouveau).read_bytes(), PDF)
            renouvelee = self.accepte("renouvelerHabilitation", br, {"date_obtention": "2026-11-02", "justificatif": nouveau})
            self.assertEqual(ligne_de(serveur.dossier, br), avant)
            self.assertEqual(valeurs(ligne_de(serveur.dossier, renouvelee), "technicien_id", "intitule", "date_obtention",
                                     "date_echeance", "recyclage_mois", "justificatif", "catalogue_id", "nature_source"),
                             (tec, "BR", "2026-11-02", "2029-11-02", "36", nouveau, "H02", "recommandation"))
            journal = [e["action"] for e in lire_csv(serveur.dossier, "journal.csv")
                       if e["table"] == "habilitations" and e["id_ligne"] == renouvelee]
            self.assertTrue(any("renouvellement de %s" % br in a and "15/01/2027 → 02/11/2029" in a for a in journal), journal)

            # Renouvellement sans justificatif : la nouvelle ligne n'en a pas, l'ancienne garde le sien
            caces = self.accepte("ajouterHabilitation", tec, {
                "intitule": "CACES R489", "date_obtention": "2022-03-01", "recyclage_mois": "60", "catalogue_id": "H12",
                "nature_source": "obligation", "justificatif": ancien})
            caces_2 = self.accepte("renouvelerHabilitation", caces, {"date_obtention": "2026-11-02"})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces_2), "date_echeance", "recyclage_mois", "justificatif",
                                     "catalogue_id", "nature_source"), ("2031-11-02", "60", "", "H12", "obligation"))
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces), "justificatif"), (ancien,))

            # Échéance calculée qui ne dépasse pas l'actuelle : refus, rien d'écrit
            chemin = serveur.dossier / "habilitations.csv"
            octets = chemin.read_bytes()
            self.refuse("dépasser", "renouvelerHabilitation", caces_2, {"date_obtention": "2026-11-01", "recyclage_mois": "12"})
            self.assertEqual(chemin.read_bytes(), octets)

            # Correction : échéance vidée et recyclage changé → recalculée ; échéance saisie gardée
            changes = self.accepte("modifierHabilitation", caces_2, {"recyclage_mois": "24", "date_echeance": ""})
            self.assertEqual(sorted(changes), ["date_echeance", "recyclage_mois"])
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces_2), "date_echeance", "recyclage_mois"),
                             ("2028-11-02", "24"))
            self.accepte("modifierHabilitation", caces_2, {"date_echeance": "2029-03-31"})
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces_2), "date_echeance"), ("2029-03-31",))
            # Correction : type et nature inconnus ramenés à vide
            changes = self.accepte("modifierHabilitation", caces_2, {"catalogue_id": "H77", "nature_source": "loi"})
            self.assertEqual(sorted(changes), ["catalogue_id", "nature_source"])
            self.assertEqual(valeurs(ligne_de(serveur.dossier, caces_2), "catalogue_id", "nature_source", "date_echeance"),
                             ("", "", "2029-03-31"))

    def test_refus_sans_rien_ecrire_et_profil_technicien(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            tec = self.nouveau_technicien("Refus")
            br = self.accepte("ajouterHabilitation", tec, {"intitule": "BR", "date_obtention": "2024-01-15",
                                                           "recyclage_mois": "36"})
            chemin = serveur.dossier / "habilitations.csv"
            documents = serveur.dossier / "documents"

            def documents_presents():
                return sorted(p.name for p in documents.iterdir()) if documents.is_dir() else []

            octets, avant_documents = chemin.read_bytes(), documents_presents()
            for recyclage in ("0", "241", "1,5", "-12", "douze"):
                with self.subTest(recyclage=recyclage):
                    self.refuse("nombre entier de mois, de 1 à 240", "ajouterHabilitation", tec,
                                {"intitule": "H0V", "date_obtention": "2024-01-15", "recyclage_mois": recyclage})
                    self.refuse("nombre entier de mois", "modifierHabilitation", br, {"recyclage_mois": recyclage})
                    self.refuse("nombre entier de mois", "renouvelerHabilitation", br,
                                {"date_obtention": "2026-11-02", "recyclage_mois": recyclage})
            self.refuse("PDF ou une photo", "ecrireJustificatif", tec, "BR", "2024-01-15",
                        fichier={"nom": "titre.txt", "type": "text/plain", "octets": list(b"texte")})
            self.refuse("PDF ou une photo", "ecrireJustificatif", tec, "BR", "2024-01-15")
            self.refuse("trop volumineux", "ecrireJustificatif", tec, "BR", "2024-01-15",
                        fichier={"nom": "gros.pdf", "type": "application/pdf", "taille": NEUF_MO + 1})
            self.assertEqual((chemin.read_bytes(), documents_presents()), (octets, avant_documents))

            # Profil technicien : seul le responsable écrit les habilitations (D195)
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte.close)
            contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            autre = contexte.new_page()
            self.surveiller(autre)
            self.ouvrir_serveur(serveur, profil="technicien", technicien_id=tec, page=autre)
            for fonction, arguments, fichier in (
                    ("ajouterHabilitation", [tec, {"intitule": "H0V", "date_obtention": "2024-01-15"}], None),
                    ("modifierHabilitation", [br, {"date_echeance": "2030-01-01"}], None),
                    ("renouvelerHabilitation", [br, {"date_obtention": "2026-11-02"}], None),
                    ("ecrireJustificatif", [tec, "BR", "2026-11-02"], fichier_pdf())):
                with self.subTest(profil="technicien", fonction=fonction):
                    self.refuse("Seul le responsable enregistre les habilitations", fonction, *arguments,
                                fichier=fichier, page=autre)
            self.assertEqual((chemin.read_bytes(), documents_presents()), (octets, avant_documents))


# ---------------------------------------------------------------------------
# Démo : noms exacts (sans horodatage), « -2 » si pris, photo réduite
# ---------------------------------------------------------------------------

class TestDemo(CasEcritures):

    def ouvrir_demo(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def test_noms_lisibles_numerotes_si_pris_et_photo_reduite(self):
        self.ouvrir_demo()
        tec = self.nouveau_technicien("Justificatifs")
        intitule = "Autorisation de conduite (employeur)"
        attendu = "habilitation-%s-Autorisation-de-conduite-employeur-2024-01-15" % tec
        noms = [self.accepte("ecrireJustificatif", tec, intitule, "2024-01-15", fichier=fichier_pdf())
                for _ in range(3)]
        self.assertEqual(noms, [attendu + ".pdf", attendu + "-2.pdf", attendu + "-3.pdf"])
        for nom in noms:
            self.assertEqual(bytes(self.page.evaluate(LIRE_DOCUMENT_JS, nom)["octets"]), PDF)
        # Accents et signes retirés du nom
        nom = self.accepte("ecrireJustificatif", tec, "Habilitation électrique « BR »", "2024-01-15", fichier=fichier_pdf())
        self.assertEqual(nom, "habilitation-%s-Habilitation-electrique-BR-2024-01-15.pdf" % tec)
        # Photo : réduite à 2 400 px de côté, enregistrée en JPEG
        nom = self.accepte("ecrireJustificatif", tec, "CACES R489", "2021-12-02",
                           fichier={"nom": "photo.png", "image": [3000, 1500]})
        self.assertEqual(nom, "habilitation-%s-CACES-R489-2021-12-02.jpg" % tec)
        lu = self.page.evaluate(LIRE_DOCUMENT_JS, nom)
        self.assertEqual((lu["debut"][:2], lu["largeur"], lu["hauteur"]), ([0xFF, 0xD8], 2400, 1200))
        # Le nom enregistré va sur la ligne
        hab = self.accepte("ajouterHabilitation", tec, {"intitule": "CACES R489", "date_obtention": "2021-12-02",
                                                        "recyclage_mois": "60", "catalogue_id": "H12",
                                                        "nature_source": "obligation", "justificatif": nom})
        self.assertEqual(self.page.evaluate("(id) => { const h = Donnees.trouver('habilitations', id); "
                                            "return [h.justificatif, h.date_echeance]; }", hab),
                         [nom, "2026-12-02"])
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", attendu + "-3.pdf"))


if __name__ == "__main__":
    unittest.main()
