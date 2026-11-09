"""Tests des écritures des garanties et des contrats de prestataires, 2.2 (garanties-ecritures.js, T452 ; CDC §3.4,
CS173, D182, D190 ; QUESTIONS-L2-L6, L4-L6 Q3, Q6 et Q12).

Par l'API (Garanties.*) dans l'application ouverte, sans passer par les écrans (T455, T456) :
    serveur  : serveur.py sur une copie temporaire du jeu de démo, profil responsable ; CSV et documents relus sur
               le disque. Une garantie créée avec son document est écrite dans garanties.csv (actif 1, document
               nommé « garantie-GAR-…-<jour>.pdf » derrière l'horodatage du serveur) avec UNE ligne de journal ;
               modifiée (champs changés seulement ; nouveau document en photo réduite, l'ancien reste) ; retirée
               (actif 0, la ligne reste ; deuxième retrait sans rien écrire ; plus modifiable). Un contrat créé
               (valeurs ramenées au format du fichier : équipements « ; », préavis entier, montant au point) est
               reconduit (période proposée ou saisie, journal « reconduction : … → … »), sa résiliation notée
               (reconduction tacite 0, date de la lettre au journal, même s'il n'y a plus rien à changer), retiré ;
               montant facultatif (D190). Refus sans rien écrire (CSV, journal, documents identiques à l'octet) :
               valeurs refusées par verifierGarantie et verifierContrat, document (type, taille), lignes
               introuvables, date de la lettre, reconduction d'un contrat sans reconduction tacite ;
    demo     : index.html en file://, écran en anglais : documents « -2 », « -3 » si le nom est pris (message du
               stockage dans la langue de l'écran), photo réduite à 2 400 px en JPEG, refus en anglais, profil autre
               que responsable refusé côté application (le serveur le refuse aussi : T453, test_droits_format4).
Aucun identifiant de garantie ni de contrat écrit en dur (le jeu de démo peut en contenir) ; dates fixes, sauf la
date du jour de l'application (Donnees.aujourdhui()), qui nomme les documents.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_ecritures.py" -v
"""
import csv
import datetime
import io
import json
import re
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

PDF = b"%PDF-1.4\n% document de test (T452)\n%%EOF\n"
NEUF_MO = 9 * 1024 * 1024

# Appel d'une fonction de Garanties ; `fichier` (facultatif) devient un File inséré à l'argument n° `position` (par
# défaut en dernier) : { nom, type, octets } ou { nom, type, taille } (zéros, en-tête PDF) ou
# { nom, image: [largeur, hauteur] } (PNG).
APPEL_JS = """async ([fonction, arguments_, fichier]) => {
  const args = arguments_.slice();
  if (fichier) {
    let contenu;
    if (fichier.image) {
      const toile = document.createElement('canvas');
      [toile.width, toile.height] = fichier.image;
      const dessin = toile.getContext('2d');
      dessin.fillStyle = '#2e86c1'; dessin.fillRect(0, 0, toile.width, toile.height);
      contenu = await new Promise((rendre) => toile.toBlob(rendre, 'image/png'));
    } else if (fichier.taille) {
      contenu = new Uint8Array(fichier.taille);
      contenu.set(new TextEncoder().encode('%PDF-1.4'));
    } else {
      contenu = new Uint8Array(fichier.octets);
    }
    const position = fichier.position === undefined ? args.length : fichier.position;
    while (args.length < position) args.push(undefined);
    args.splice(position, 0, new File([contenu], fichier.nom, { type: fichier.type || '' }));
  }
  try { return 'accepté:' + JSON.stringify(await Garanties[fonction](...args)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""

# Document relu par l'adaptateur (mode démo) : { octets | largeur, hauteur, debut }.
LIRE_DOCUMENT_JS = """async (nom) => {
  const blob = await App.adaptateur.lireDocument(nom);
  if (!blob) return null;
  const octets = Array.from(new Uint8Array(await blob.arrayBuffer()));
  const resultat = { debut: octets.slice(0, 3) };
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


def ligne_de(dossier, nom, identifiant):
    return {cle: brut(v) for cle, v in next(l for l in lire_csv(dossier, nom) if l["id"] == identifiant).items()}


def journal(dossier, table, identifiant):
    return [e["action"] for e in lire_csv(dossier, "journal.csv") if e["table"] == table and e["id_ligne"] == identifiant]


def fichier_pdf(nom="certificat.pdf", position=None):
    fichier = {"nom": nom, "type": "application/pdf", "octets": list(PDF)}
    if position is not None:
        fichier["position"] = position
    return fichier


class CasGaranties(CasNavigateur):

    def ouvrir_serveur(self, serveur):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def appeler(self, fonction, *arguments, fichier=None):
        return self.page.evaluate(APPEL_JS, [fonction, list(arguments), fichier])

    def accepte(self, fonction, *arguments, fichier=None):
        resultat = self.appeler(fonction, *arguments, fichier=fichier)
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def refuse(self, attendu, fonction, *arguments, fichier=None):
        resultat = self.appeler(fonction, *arguments, fichier=fichier)
        self.assertTrue(resultat.startswith("refus:") and attendu in resultat, (attendu, resultat))

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))


def equipements_et_fournisseur(dossier):
    """Deux équipements et un fournisseur du jeu copié (aucun identifiant écrit en dur)."""
    equipements = [e["id"] for e in lire_csv(dossier, "equipements.csv")]
    fournisseurs = [f["id"] for f in lire_csv(dossier, "fournisseurs.csv")]
    return equipements[0], equipements[1], fournisseurs[0]


# ---------------------------------------------------------------------------
# Serveur : CSV, journal et documents relus sur le disque
# ---------------------------------------------------------------------------

class TestServeur(CasGaranties):

    def test_garantie_creee_avec_document_modifiee_puis_retiree(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            dossier = serveur.dossier
            documents = dossier / "documents"
            eq, _, fou = equipements_et_fournisseur(dossier)
            jour = self.aujourdhui().isoformat()

            # Création avec le certificat : identifiant, actif et document imposés par l'écriture
            gar = self.accepte("creerGarantie", {
                "id": "GAR-9999", "actif": "0", "equipement_id": eq, "fournisseur_id": fou, "date_debut": "01/06/2025",
                "date_fin": "2027-05-31", "conditions": "  Pièces et main-d'œuvre, hors pièces d'usure  "},
                fichier=fichier_pdf(position=1))
            self.assertRegex(gar, r"^GAR-\d{4}$")
            self.assertNotEqual(gar, "GAR-9999")
            ligne = ligne_de(dossier, "garanties.csv", gar)
            nom = ligne["document"]
            self.assertRegex(nom, r"^\d{8}-\d{6}-garantie-%s-%s\.pdf$" % (gar, jour))
            self.assertEqual((documents / nom).read_bytes(), PDF)
            self.assertEqual({c: ligne[c] for c in ("equipement_id", "fournisseur_id", "date_debut", "date_fin",
                                                    "conditions", "actif")},
                             {"equipement_id": eq, "fournisseur_id": fou, "date_debut": "2025-06-01",
                              "date_fin": "2027-05-31", "conditions": "Pièces et main-d'œuvre, hors pièces d'usure",
                              "actif": "1"})
            self.assertEqual(journal(dossier, "garanties", gar), ["création — garantie enregistrée ; document : " + nom])

            # Modification : seuls les champs changés ; les mêmes valeurs redonnées n'écrivent rien
            self.assertEqual(self.accepte("modifierGarantie", gar, {"fournisseur_id": "", "date_fin": "2027-06-30"}),
                             ["fournisseur_id", "date_fin"])
            self.assertEqual(journal(dossier, "garanties", gar)[-1],
                             "modification : fournisseur_id, date_fin — modification de la garantie")
            chemin = dossier / "garanties.csv"
            octets = chemin.read_bytes()
            self.assertEqual(self.accepte("modifierGarantie", gar, {"fournisseur_id": " ", "date_fin": "30/06/2027"}), [])
            self.assertEqual(chemin.read_bytes(), octets)
            self.assertEqual(len(journal(dossier, "garanties", gar)), 2)

            # Nouveau document (photo) : réduit en JPEG, nommé sur la ligne ; l'ancien reste dans les documents
            changes = self.accepte("modifierGarantie", gar, {}, fichier={"nom": "facture.png", "image": [3000, 1500],
                                                                          "position": 2})
            self.assertEqual(changes, ["document"])
            photo = ligne_de(dossier, "garanties.csv", gar)["document"]
            self.assertRegex(photo, r"^\d{8}-\d{6}-garantie-%s-%s\.jpg$" % (gar, jour))
            self.assertEqual((documents / photo).read_bytes()[:2], b"\xff\xd8")
            self.assertEqual((documents / nom).read_bytes(), PDF)
            self.assertEqual(journal(dossier, "garanties", gar)[-1],
                             "modification : document — modification de la garantie ; document : " + photo)

            # Retirer : actif à 0, la ligne reste (rien n'est effacé) ; un second retrait n'écrit rien
            nombre = len(lire_csv(dossier, "garanties.csv"))
            avant = ligne_de(dossier, "garanties.csv", gar)
            self.assertEqual(self.accepte("retirerGarantie", gar), ["actif"])
            apres = ligne_de(dossier, "garanties.csv", gar)
            self.assertEqual(apres, dict(avant, actif="0"))
            self.assertEqual(len(lire_csv(dossier, "garanties.csv")), nombre)
            self.assertEqual(journal(dossier, "garanties", gar)[-1], "modification : actif — garantie retirée")
            octets = chemin.read_bytes()
            self.assertEqual(self.accepte("retirerGarantie", gar), [])
            self.refuse("La garantie %s est retirée" % gar, "modifierGarantie", gar, {"conditions": "x"})
            self.assertEqual(chemin.read_bytes(), octets)
            self.assertEqual(len(journal(dossier, "garanties", gar)), 4)

    def test_resiliation_refusee_si_fin_passee_puis_acceptee_apres_reconduction(self):
        """T464 : contrat tacite « dates à mettre à jour » : la lettre est refusée, rien n'est écrit."""
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            dossier = serveur.dossier
            chemin = dossier / "contrats_prestataires.csv"
            _eq1, _eq2, fou = equipements_et_fournisseur(dossier)
            jour = self.aujourdhui()
            ctp = self.accepte("creerContrat", {"fournisseur_id": fou, "objet": "Contrat échu", "date_debut": "2020-01-01",
                                                "date_fin": "2020-12-31", "preavis_mois": "3", "reconduction_tacite": True})
            octets = chemin.read_bytes()
            entrees = len(journal(dossier, "contrats_prestataires", ctp))
            self.refuse("Reconduisez d'abord le contrat à sa période en cours", "noterResiliation", ctp,
                        {"date": jour.isoformat()})
            self.assertEqual(chemin.read_bytes(), octets)
            self.assertEqual(len(journal(dossier, "contrats_prestataires", ctp)), entrees)
            self.assertEqual(ligne_de(dossier, "contrats_prestataires.csv", ctp)["reconduction_tacite"], "1")
            # Reconduit à une période en cours (fin dans le futur) : la lettre est acceptée
            futur = (jour + datetime.timedelta(days=400)).isoformat()
            self.accepte("reconduireContrat", ctp, {"date_debut": jour.isoformat(), "date_fin": futur})
            self.assertEqual(self.accepte("noterResiliation", ctp, {"date": jour.isoformat()}), ["reconduction_tacite"])

    def test_contrat_reconduit_resiliation_notee_et_retire(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            dossier = serveur.dossier
            chemin = dossier / "contrats_prestataires.csv"
            eq1, eq2, fou = equipements_et_fournisseur(dossier)
            jour = self.aujourdhui()

            # Création : valeurs ramenées au format du fichier, contrat signé joint
            ctp = self.accepte("creerContrat", {
                "fournisseur_id": fou, "objet": " Maintenance préventive des compresseurs ",
                "equipement_ids": [eq1, " " + eq2, eq1], "perimetre": "Deux visites par an", "date_debut": "2026-01-01",
                "date_fin": "2026-12-31", "preavis_mois": "03", "reconduction_tacite": True, "reconduction_mois": "12,0",
                "montant_annuel": "4 800,50"}, fichier=fichier_pdf("Contrat signé.PDF", position=1))
            self.assertRegex(ctp, r"^CTP-\d{4}$")
            ligne = ligne_de(dossier, "contrats_prestataires.csv", ctp)
            nom = ligne["document"]
            self.assertRegex(nom, r"^\d{8}-\d{6}-contrat-%s-%s\.pdf$" % (ctp, jour.isoformat()))
            self.assertEqual((dossier / "documents" / nom).read_bytes(), PDF)
            self.assertEqual({c: ligne[c] for c in ("fournisseur_id", "objet", "equipement_ids", "perimetre",
                                                    "date_debut", "date_fin", "preavis_mois", "reconduction_tacite",
                                                    "reconduction_mois", "montant_annuel", "actif")},
                             {"fournisseur_id": fou, "objet": "Maintenance préventive des compresseurs",
                              "equipement_ids": eq1 + ";" + eq2, "perimetre": "Deux visites par an",
                              "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_mois": "3",
                              "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "4800.50",
                              "actif": "1"})
            self.assertEqual(journal(dossier, "contrats_prestataires", ctp),
                             ["création — contrat enregistré ; document : " + nom])

            # Reconduire : période proposée (fin + 1 jour, 12 mois), puis période saisie
            self.assertEqual(self.accepte("reconduireContrat", ctp),
                             {"date_debut": "2027-01-01", "date_fin": "2027-12-31"})
            ligne = ligne_de(dossier, "contrats_prestataires.csv", ctp)
            self.assertEqual((ligne["date_debut"], ligne["date_fin"], ligne["reconduction_tacite"]),
                             ("2027-01-01", "2027-12-31", "1"))
            self.assertEqual(journal(dossier, "contrats_prestataires", ctp)[-1],
                             "modification : date_debut, date_fin — reconduction : du 01/01/2026 au 31/12/2026 "
                             "→ du 01/01/2027 au 31/12/2027")
            self.assertEqual(self.accepte("reconduireContrat", ctp, {"date_debut": "2028-01-01", "date_fin": "30/06/2028"}),
                             {"date_debut": "2028-01-01", "date_fin": "2028-06-30"})
            self.assertTrue(journal(dossier, "contrats_prestataires", ctp)[-1].endswith(
                "reconduction : du 01/01/2027 au 31/12/2027 → du 01/01/2028 au 30/06/2028"))
            octets = chemin.read_bytes()
            self.refuse("La nouvelle date de fin doit être après la fin actuelle (30/06/2028)", "reconduireContrat", ctp,
                        {"date_debut": "2028-01-01", "date_fin": "2028-06-30"})
            self.assertEqual(chemin.read_bytes(), octets)

            # Noter la résiliation : reconduction tacite à 0, date de la lettre et commentaire au journal
            lettre = (jour - datetime.timedelta(days=3)).isoformat()
            self.assertEqual(self.accepte("noterResiliation", ctp, {"date": lettre,
                                                                    "commentaire": "Lettre recommandée avec AR"}),
                             ["reconduction_tacite"])
            self.assertEqual(ligne_de(dossier, "contrats_prestataires.csv", ctp)["reconduction_tacite"], "0")
            texte_lettre = "résiliation notée : lettre du %s" % datetime.date.fromisoformat(lettre).strftime("%d/%m/%Y")
            self.assertEqual(journal(dossier, "contrats_prestataires", ctp)[-1],
                             "modification : reconduction_tacite — " + texte_lettre + " ; Lettre recommandée avec AR")
            # Plus de reconduction tacite : « Reconduire » refusé ; une seconde lettre ne change rien à la ligne,
            # mais sa trace est écrite au journal
            self.refuse("ne se reconduit pas tacitement", "reconduireContrat", ctp)
            octets = chemin.read_bytes()
            self.assertEqual(self.accepte("noterResiliation", ctp, {"date": jour.isoformat()}), [])
            self.assertEqual(chemin.read_bytes(), octets)
            self.assertEqual(journal(dossier, "contrats_prestataires", ctp)[-1],
                             "résiliation notée : lettre du %s" % jour.strftime("%d/%m/%Y"))

            # Contrat sans montant (D190 : facultatif), sans équipement ni document
            libre = self.accepte("creerContrat", {"fournisseur_id": fou, "objet": "Thermographie des armoires",
                                                  "date_fin": "2026-12-31"})
            ligne = ligne_de(dossier, "contrats_prestataires.csv", libre)
            self.assertEqual((ligne["montant_annuel"], ligne["equipement_ids"], ligne["reconduction_tacite"],
                              ligne["document"], ligne["actif"]), ("", "", "0", "", "1"))
            self.assertEqual(journal(dossier, "contrats_prestataires", libre), ["création — contrat enregistré"])
            self.assertEqual(self.accepte("modifierContrat", libre, {"montant_annuel": "1350", "reconduction_tacite": "oui",
                                                                     "equipement_ids": eq2 + ", " + eq1}),
                             ["equipement_ids", "reconduction_tacite", "montant_annuel"])
            self.assertEqual(ligne_de(dossier, "contrats_prestataires.csv", libre)["equipement_ids"], eq2 + ";" + eq1)

            # Retirer : actif à 0, la ligne reste ; plus rien ne s'y écrit
            self.assertEqual(self.accepte("retirerContrat", libre), ["actif"])
            self.assertEqual(ligne_de(dossier, "contrats_prestataires.csv", libre)["actif"], "0")
            self.assertEqual(journal(dossier, "contrats_prestataires", libre)[-1], "modification : actif — contrat retiré")
            octets = chemin.read_bytes()
            self.assertEqual(self.accepte("retirerContrat", libre), [])
            self.refuse("Le contrat %s est retiré" % libre, "noterResiliation", libre, {"date": jour.isoformat()})
            self.refuse("Le contrat %s est retiré" % libre, "reconduireContrat", libre)
            self.assertEqual(chemin.read_bytes(), octets)

    def test_refus_sans_rien_ecrire(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_serveur(serveur)
            dossier = serveur.dossier
            documents = dossier / "documents"
            eq, _, fou = equipements_et_fournisseur(dossier)
            gar = self.accepte("creerGarantie", {"equipement_id": eq, "date_fin": "2027-05-31"})
            ctp = self.accepte("creerContrat", {"fournisseur_id": fou, "objet": "Nettoyage", "date_fin": "2026-12-31",
                                                "reconduction_tacite": "1"})
            demain = (self.aujourdhui() + datetime.timedelta(days=1)).isoformat()

            def etat():
                noms = sorted(p.name for p in documents.iterdir()) if documents.is_dir() else []
                return [(dossier / n).read_bytes() for n in ("garanties.csv", "contrats_prestataires.csv",
                                                             "journal.csv")] + [noms]

            avant = etat()
            # Garanties : verifierGarantie (avec un document joint : il n'est pas écrit non plus)
            for valeurs, attendu in (
                    ({}, "Choisissez l'équipement couvert"),
                    ({"equipement_id": "EQ-9999", "date_fin": "2027-01-01"}, "L'équipement EQ-9999 est introuvable"),
                    ({"equipement_id": eq}, "Saisissez la date de fin de la garantie"),
                    ({"equipement_id": eq, "date_fin": "2027-02-30"}, "Date de fin illisible"),
                    ({"equipement_id": eq, "date_debut": "2027-01-02", "date_fin": "2027-01-01"}, "ne peut pas précéder"),
                    ({"equipement_id": eq, "date_fin": "2027-01-01", "fournisseur_id": "FOU-9999"}, "FOU-9999 est introuvable")):
                with self.subTest(garantie=valeurs):
                    self.refuse(attendu, "creerGarantie", valeurs, fichier=fichier_pdf(position=1))
            self.refuse("Saisissez la date de fin de la garantie", "modifierGarantie", gar, {"date_fin": ""},
                        fichier=fichier_pdf(position=2))
            # Document : PDF, JPEG ou PNG seulement ; taille
            for nom in ("certificat.txt", "photo.gif", "photo.webp", "sans-extension"):
                with self.subTest(document=nom):
                    self.refuse("Le document doit être un PDF, un JPEG ou un PNG", "creerGarantie",
                                {"equipement_id": eq, "date_fin": "2027-01-01"},
                                fichier={"nom": nom, "type": "", "octets": list(b"x"), "position": 1})
                    self.refuse("un PDF, un JPEG ou un PNG", "ecrireDocument", gar,
                                fichier={"nom": nom, "type": "", "octets": list(b"x"), "position": 1})
            self.refuse("trop volumineux", "ecrireDocument", ctp,
                        fichier={"nom": "gros.pdf", "type": "application/pdf", "taille": NEUF_MO + 1, "position": 1})
            self.refuse("un PDF, un JPEG ou un PNG", "ecrireDocument", gar)
            self.refuse("La garantie GAR-9999 est introuvable", "ecrireDocument", "GAR-9999", fichier=fichier_pdf(position=1))
            self.refuse("Le contrat CTP-9999 est introuvable", "ecrireDocument", "CTP-9999", fichier=fichier_pdf(position=1))
            # Contrats : verifierContrat
            base = {"fournisseur_id": fou, "objet": "Nettoyage", "date_fin": "2026-12-31"}
            for valeurs, attendu in (
                    ({}, "Choisissez le prestataire"),
                    (dict(base, fournisseur_id="FOU-9999"), "Le prestataire FOU-9999 est introuvable"),
                    (dict(base, objet="  "), "Saisissez l'objet du contrat"),
                    (dict(base, date_fin=""), "Saisissez la date de fin de la période en cours"),
                    (dict(base, preavis_mois="-1"), "Préavis : un nombre entier de mois"),
                    (dict(base, preavis_mois="1,5"), "Préavis : un nombre entier de mois"),
                    (dict(base, preavis_mois="trois"), "Préavis : un nombre entier de mois"),
                    (dict(base, reconduction_mois="0"), "Durée d'une reconduction : un nombre entier de mois"),
                    (dict(base, montant_annuel="-5"), "Montant : un nombre positif, ou rien"),
                    (dict(base, montant_annuel="beaucoup"), "Montant : un nombre positif, ou rien"),
                    (dict(base, equipement_ids=[eq, "EQ-9999"]), "L'équipement EQ-9999 est introuvable")):
                with self.subTest(contrat=valeurs):
                    self.refuse(attendu, "creerContrat", valeurs, fichier=fichier_pdf(position=1))
            self.refuse("Montant : un nombre positif", "modifierContrat", ctp, {"montant_annuel": "-1"})
            # Lignes introuvables
            for fonction, arguments, attendu in (
                    ("modifierGarantie", ["GAR-9999", {}], "La garantie GAR-9999 est introuvable"),
                    ("retirerGarantie", ["GAR-9999"], "La garantie GAR-9999 est introuvable"),
                    ("modifierContrat", ["CTP-9999", {}], "Le contrat CTP-9999 est introuvable"),
                    ("retirerContrat", ["CTP-9999"], "Le contrat CTP-9999 est introuvable"),
                    ("reconduireContrat", ["CTP-9999"], "Le contrat CTP-9999 est introuvable"),
                    ("noterResiliation", ["CTP-9999", {"date": "2026-01-01"}], "Le contrat CTP-9999 est introuvable")):
                with self.subTest(fonction=fonction):
                    self.refuse(attendu, fonction, *arguments)
            # Résiliation : date de la lettre obligatoire, lisible, pas dans le futur
            for valeurs, attendu in (({}, "Saisissez la date d'envoi de la lettre"),
                                     ({"date": "2026-13-01"}, "Date d'envoi illisible"),
                                     ({"date": demain}, "ne peut pas être dans le futur")):
                with self.subTest(resiliation=valeurs):
                    self.refuse(attendu, "noterResiliation", ctp, valeurs)
            # Reconduction : dates de la nouvelle période
            self.refuse("Saisissez la date de fin de la période en cours", "reconduireContrat", ctp, {"date_fin": ""})
            self.refuse("ne peut pas précéder", "reconduireContrat", ctp, {"date_debut": "2028-01-01", "date_fin": "2027-12-31"})
            self.refuse("Date de fin illisible", "reconduireContrat", ctp, {"date_fin": "2027-02-30"})
            self.assertEqual(etat(), avant)


# ---------------------------------------------------------------------------
# Démo en anglais : noms numérotés, photo réduite, refus dans la langue de l'écran, profil
# ---------------------------------------------------------------------------

class TestDemoAnglais(CasGaranties):

    def test_documents_numerotes_photo_reduite_et_refus_en_anglais(self):
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        preregler_profil(self.contexte, "responsable")
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("I18n.langue"), "en")
        jour = self.aujourdhui().isoformat()
        eq = self.page.evaluate("Donnees.lignes('equipements')[0].id")
        fou = self.page.evaluate("Donnees.lignes('fournisseurs')[0].id")

        # Garantie créée avec son document : ligne et journal en mémoire
        gar = self.accepte("creerGarantie", {"equipement_id": eq, "date_fin": "2027-05-31"}, fichier=fichier_pdf(position=1))
        base = "garantie-%s-%s" % (gar, jour)
        lue = self.page.evaluate("""async (id) => {
          await Donnees.rechargerTable('journal');
          return { document: Donnees.trouver('garanties', id).document,
            journal: Donnees.lignes('journal').filter((e) => e.table === 'garanties' && e.id_ligne === id).map((e) => e.action) };
        }""", gar)
        self.assertEqual(lue, {"document": base + ".pdf", "journal": ["création — garantie enregistrée ; document : %s.pdf" % base]})
        # Le même nom pris : « -2 », « -3 » (le stockage le refuse par un message dans la langue de l'écran)
        noms = [self.accepte("ecrireDocument", gar, fichier=fichier_pdf(position=1)) for _ in range(2)]
        self.assertEqual(noms, [base + "-2.pdf", base + "-3.pdf"])
        for nom in [base + ".pdf"] + noms:
            self.assertEqual(bytes(self.page.evaluate(LIRE_DOCUMENT_JS, nom)["octets"]), PDF)
        # Photo : réduite à 2 400 px de côté, enregistrée en JPEG ; date du nom donnée
        nom = self.accepte("ecrireDocument", gar, "2026-11-08", fichier={"nom": "photo.JPG", "image": [1500, 3000],
                                                                         "position": 1})
        self.assertEqual(nom, "garantie-%s-2026-11-08.jpg" % gar)
        lu = self.page.evaluate(LIRE_DOCUMENT_JS, nom)
        self.assertEqual((lu["debut"][:2], lu["largeur"], lu["hauteur"]), ([0xFF, 0xD8], 1200, 2400))
        # Contrat et son document
        ctp = self.accepte("creerContrat", {"fournisseur_id": fou, "objet": "Compressor maintenance", "date_fin": "2026-12-31"},
                           fichier=fichier_pdf("contract.pdf", position=1))
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('contrats_prestataires', id).document", ctp),
                         "contrat-%s-%s.pdf" % (ctp, jour))

        # Refus dans la langue de l'écran
        self.refuse("Choose the equipment covered.", "creerGarantie", {})
        self.refuse("The document must be a PDF, a JPEG or a PNG.", "ecrireDocument", gar,
                    fichier={"nom": "notes.txt", "type": "text/plain", "octets": list(b"x"), "position": 1})
        self.refuse("This contract does not renew automatically", "reconduireContrat", ctp)
        self.refuse("Enter the date the letter was sent.", "noterResiliation", ctp, {})
        self.refuse("Warranty GAR-9999 not found.", "retirerGarantie", "GAR-9999")

        # Profil autre que responsable : rien d'écrit (côté application ; le serveur le refuse aussi, T453)
        self.page.evaluate("() => { window.__estResponsable = App.estResponsable; App.estResponsable = () => false; }")
        try:
            for fonction, arguments, fichier in (
                    ("creerGarantie", [{"equipement_id": eq, "date_fin": "2027-05-31"}], None),
                    ("modifierGarantie", [gar, {"conditions": "x"}], None),
                    ("retirerGarantie", [gar], None),
                    ("creerContrat", [{"fournisseur_id": fou, "objet": "x", "date_fin": "2026-12-31"}], None),
                    ("modifierContrat", [ctp, {"objet": "x"}], None),
                    ("retirerContrat", [ctp], None),
                    ("reconduireContrat", [ctp], None),
                    ("noterResiliation", [ctp, {"date": jour}], None),
                    ("ecrireDocument", [gar], fichier_pdf(position=1))):
                with self.subTest(profil="technicien", fonction=fonction):
                    self.refuse("Only the manager can record warranties and contracts.", fonction, *arguments,
                                fichier=fichier)
        finally:
            self.page.evaluate("() => { App.estResponsable = window.__estResponsable; }")
        etat = self.page.evaluate("""([gar, ctp]) => [Donnees.trouver('garanties', gar).actif,
          Donnees.trouver('contrats_prestataires', ctp).objet]""", [gar, ctp])
        self.assertEqual(etat, ["1", "Compressor maintenance"])
        # Noms acceptés par la règle des noms de documents du serveur
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", base + "-3.pdf"))


if __name__ == "__main__":
    unittest.main()
