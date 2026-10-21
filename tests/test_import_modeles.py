"""Modèles à remplir de l'assistant d'import (tâche T84, ARCHITECTURE.md §18.8 ; CS90).

Pour chaque type de données (Import.TYPES) et chaque format (.xlsx, .csv) :
  - le modèle se lit : en Python sans SheetJS (zipfile + XML pour le .xlsx, module csv pour le .csv : BOM,
    « ; », CRLF) et par Import.lire ; feuille « Données » = titres en libellés + ligne d'exemple, feuille
    « Aide » = une ligne par colonne (obligatoire, format, valeurs permises, exemple) ;
  - ses titres sont tous reconnus par Import.correspondance (statut « sure ») ;
  - sa ligne d'exemple s'importe sans refus sur la base de démo (aperçu sans ligne refusée, puis
    Import.importer et Import.annuler).
L'historique n'est essayé que si Import.preparerHistorique existe (tâche T82).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_modeles.py" -v
"""
import base64
import csv
import io
import tempfile
import unittest
from pathlib import Path

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_fixtures_import import lire_xlsx

MAINTENANT = "2026-10-21 09:30"

# Modèle écrit dans la page (base64), relu par Import.lire, reconnu, aperçu puis importé et annulé.
ESSAYER_JS = """async ([type, format, maintenant]) => {
  const blob = await Import.modele(type, format);
  const octets = new Uint8Array(await blob.arrayBuffer());
  let binaire = '';
  octets.forEach((o) => { binaire += String.fromCharCode(o); });
  const lu = await Import.lire(new File([octets], Import.nomModele(type, format)));
  const lignes = lu.feuilles[0].lignes;
  const correspondance = Import.correspondance(type, lignes[0], lignes.slice(1), null);
  const apercu = Import.preparer(type, lignes.slice(1), correspondance, { maintenant, mettreAJour: true });
  const resultat = { base64: btoa(binaire), mime: blob.type, nom: Import.nomModele(type, format),
    feuilles: lu.feuilles.map((f) => f.nom), lignes,
    statuts: correspondance.map((c) => [c.entete, c.champ, c.statut]),
    actions: apercu.lignes.map((l) => [l.action, l.raisons]), totaux: apercu.totaux };
  if (format === 'xlsx' && apercu.lignes.some((l) => l.action === 'creer' || l.action === 'mettre_a_jour')) {
    const tables = () => Object.entries(Donnees.instantane()).filter(([nom]) => nom !== 'journal')
      .map(([nom, o]) => nom + ':' + Array.from(o).join(',')).join(';');
    const avant = tables();
    const ecrit = await Import.importer(apercu, { nomFichier: resultat.nom });
    resultat.tables = ecrit.tables;
    await Import.annuler(ecrit);
    resultat.annule = tables() === avant;
  }
  return resultat;
}"""


class TestModeles(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.types = self.page.evaluate("""() => Object.values(Import.TYPES).map((t) => ({ cle: t.cle,
          titres: t.champs.map((c) => c.libelle), exemples: t.champs.map((c) => c.exemple === undefined ? '' : String(c.exemple)) }))""")
        self.historique = self.page.evaluate("typeof Import.preparerHistorique === 'function'")

    def essayer(self, type_, format_):
        return self.page.evaluate(ESSAYER_JS, [type_, format_, MAINTENANT])

    def test_chaque_modele_se_lit_est_reconnu_et_s_importe_sans_refus(self):
        self.assertGreaterEqual(len(self.types), 11)
        for definition in self.types:
            type_ = definition["cle"]
            if type_ == "historique" and not self.historique:
                continue
            for format_ in ("xlsx", "csv"):
                with self.subTest(type=type_, format=format_):
                    essai = self.essayer(type_, format_)
                    octets = base64.b64decode(essai["base64"])
                    self.assertEqual(essai["nom"], "prevo-modele-%s.%s" % (type_, format_))
                    attendu = [definition["titres"], definition["exemples"]]
                    if format_ == "xlsx":
                        self.assertEqual(octets[:2], b"PK")
                        with tempfile.TemporaryDirectory() as dossier:
                            chemin = Path(dossier) / essai["nom"]
                            chemin.write_bytes(octets)
                            grilles, _brutes, _formats = lire_xlsx(chemin)
                        self.assertEqual(list(grilles), ["Données", "Aide"])
                        self.assertEqual([l + [""] * (len(definition["titres"]) - len(l)) for l in grilles["Données"]], attendu)
                        aide = grilles["Aide"]
                        entete = aide.index(["Colonne", "Obligatoire", "Format", "Valeurs permises", "Exemple", "Autres titres reconnus"])
                        self.assertEqual([l[0] for l in aide[entete + 1:]], definition["titres"])
                        self.assertEqual(essai["feuilles"], ["Données", "Aide"])
                    else:
                        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"), "BOM")
                        texte = octets.decode("utf-8-sig")
                        self.assertTrue(texte.endswith("\r\n"))
                        self.assertEqual(texte.count("\r\n"), 2)
                        relu = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
                        relu = [[c[1:] if c.startswith("'") else c for c in ligne] for ligne in relu]
                        self.assertEqual(relu, attendu)
                    # Import.lire rend les cellules brutes : l'apostrophe de protection du CSV de Prévo
                    # (« '365 ») n'est retirée qu'à la conversion, par Import.preparer.
                    lus = [[c[1:] if format_ == "csv" and c.startswith("'") else c for c in l] for l in essai["lignes"][:2]]
                    self.assertEqual(lus, attendu, "Import.lire relit le modèle")
                    non_reconnus = [s for s in essai["statuts"] if s[2] != "sure"]
                    self.assertEqual(non_reconnus, [], "chaque titre du modèle est reconnu")
                    refusees = [a for a in essai["actions"] if a[0] == "refusee"]
                    self.assertEqual(refusees, [], "la ligne d'exemple s'importe sans refus")
                    self.assertEqual(len(essai["actions"]), 1)
                    if format_ == "xlsx" and "tables" in essai:
                        self.assertTrue(essai["annule"])

    def test_type_ou_format_inconnu(self):
        messages = self.page.evaluate("""async () => {
          const r = [];
          for (const essai of [() => Import.modele('inconnu', 'xlsx'), () => Import.modele('articles', 'pdf')]) {
            try { await essai(); r.push('pas d\\'erreur'); } catch (e) { r.push(e.name + ' ' + e.message); }
          }
          return r;
        }""")
        self.assertIn("ErreurImport Type de données inconnu", messages[0])
        self.assertIn("ErreurImport Format de modèle inconnu", messages[1])


if __name__ == "__main__":
    unittest.main()
