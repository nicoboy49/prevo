"""Restes de la relecture critique du 12/11 (chantier 2.2, T509 ; rapports R1 et R2 ; docs/FORMAT.md §3.2,
docs/ARCHITECTURE.md §18.7). Sans navigateur : serveur réel de tests/commun.py, et Node pour le miroir du navigateur.

    1. Reprise des réserves (étape 3 → 4, D183) : une derniere_date illisible qui commence par =, +, - ou @ était
       recopiée telle quelle dans reserves_controle.date_controle ; le serveur refusait ensuite toute écriture de la
       table (400, contrôle des formules). Elle reçoit l'apostrophe de protection, des deux côtés :
         - serveur : passage au démarrage sur une copie du jeu « f3-v2.1.0 » complétée de contrôles aux
           dates illisibles ; cellules attendues ; PUT /api/csv/reserves_controle du fichier écrit : 200 ;
         - navigateur (Node : js/formats.js et js/donnees.js, adaptateur en mémoire) : Donnees.migrerAuFormatCourant
           sur la même base ; chaque CSV (hors journal, horodaté) identique à l'octet à celui du serveur.
    2. « Tester une sauvegarde » (POST /api/sauvegarde/tester) : un CSV abîmé (guillemet jamais fermé, valeurs au-delà
       de l'en-tête), que le manifeste de la sauvegarde marque « abime », est signalé : ok faux, erreur sur sa table.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_restes_relecture.py" -v
"""
import hashlib
import http.client
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, ServeurPrevo
from jeux_formats import copier_jeu

BOM = b"\xef\xbb\xbf"
CRLF = b"\r\n"

# derniere_date du contrôle ajouté → date_controle attendue de sa réserve.
DATES = [
    ("-", "'-"),
    ("=1+1", "'=1+1"),
    ("+33", "'+33"),
    ("@cmd", "'@cmd"),
    ("-5", "'-5"),
    ("- voir rapport", "'- voir rapport"),
    ("hier", "hier"),                   # témoins : texte sans danger gardé tel quel, date reconnue normalisée
    ("?", "?"),
    ("31/12/2025", "2025-12-31"),
    ("2025-02-30", "2025-02-30"),
]

# Migration par le code du navigateur, sous Node : scripts du dépôt chargés dans un contexte, adaptateur en mémoire
# (mode dossier), Donnees.migrerAuFormatCourant, puis les fichiers écrits dans le dossier de sortie.
SCRIPT_NODE = r"""
const fs = require('fs'), path = require('path'), vm = require('vm'), crypto = require('crypto');
const [racine, entree, sortie] = process.argv.slice(2);
const ctx = { console, TextDecoder, TextEncoder, EventTarget, CustomEvent, Intl, setTimeout, clearTimeout,
              crypto: globalThis.crypto, Event };
ctx.self = ctx; ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['js/lib/papaparse.min.js', 'js/i18n.js', 'js/i18n/langues.js', 'js/i18n/fr.js', 'js/schema.js',
                 'js/formats.js', 'js/donnees.js']) {
  vm.runInContext(fs.readFileSync(path.join(racine, f), 'utf8'), ctx, { filename: f });
}
const fichiers = new Map();
for (const nom of fs.readdirSync(entree)) {
  if (nom.endsWith('.csv')) fichiers.set(nom.slice(0, -4), new Uint8Array(fs.readFileSync(path.join(entree, nom))));
}
const emp = (o) => crypto.createHash('sha256').update(o).digest('hex');
ctx.__adaptateur = {
  mode: 'dossier',
  async charger(t) { const o = fichiers.get(t); return o ? { octets: o, version: emp(o) } : { octets: null, version: null }; },
  async enregistrer(t, octets, version) {
    const o = fichiers.get(t); const v = o ? emp(o) : null;
    if (v !== (version === undefined ? null : version)) { throw new Error('conflit de version sur ' + t); }
    fichiers.set(t, new Uint8Array(octets)); return { version: emp(octets) };
  },
  async ajouter(t, octets) {
    const o = fichiers.get(t) || new Uint8Array(0); const tout = new Uint8Array(o.length + octets.length);
    tout.set(o); tout.set(new Uint8Array(octets), o.length); fichiers.set(t, tout); return { version: emp(tout) };
  },
  async sauvegarder(motif) { return '2026-11-12_000000_' + motif; },
};
(async () => {
  const r = await vm.runInContext(`(async () => {
    Donnees.initialiser(__adaptateur, { poste: 'P', profil: '' }); await Donnees.chargerTout();
    let erreur = null; try { await Donnees.migrerAuFormatCourant(); } catch (e) { erreur = String(e && e.message); }
    await Donnees.chargerTout();
    return JSON.stringify({ erreur, format: Donnees.parametre('version_schema'),
      dates: Donnees.lignes('reserves_controle').map((l) => [l.controle_id, l.date_controle]) }); })()`, ctx);
  fs.mkdirSync(sortie, { recursive: true });
  for (const [t, o] of fichiers) fs.writeFileSync(path.join(sortie, t + '.csv'), o);
  console.log(r);
})().catch((e) => { console.error('ERREUR', e); process.exit(1); });
"""


def requete(serveur, methode, chemin, corps=b"", entetes=None):
    """(statut, objet JSON) d'une requête au serveur de test."""
    if not isinstance(corps, bytes):
        corps = json.dumps(corps).encode("utf-8")
    tous = {"X-Prevo": "1", "Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(corps))}
    tous.update(entetes or {})
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=tous)
        reponse = connexion.getresponse()
        return reponse.status, json.loads(reponse.read().decode("utf-8") or "null")
    finally:
        connexion.close()


def lignes_csv(octets):
    """Lignes d'un CSV simple de Prévo (sans cellule entre guillemets) : listes de cellules, en-tête compris."""
    return [ligne.split(";") for ligne in octets[len(BOM):].decode("utf-8").split("\r\n") if ligne]


class CasTemporaire(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t509-"))
        self.addCleanup(shutil.rmtree, str(self.temporaire), True)


class TestDateIllisibleALaReprise(CasTemporaire):

    def base(self):
        """Copie du jeu « f3-v2.1.0 » (format 3, sans colonne inconnue) plus un contrôle par date de DATES, chacun
        avec une observation."""
        dossier = copier_jeu("f3-v2.1.0", self.temporaire / "base")
        chemin = dossier / "controles_reglementaires.csv"
        octets = chemin.read_bytes()
        colonnes = octets[len(BOM):].split(CRLF, 1)[0].decode("utf-8").split(";")
        ajout = []
        for numero, (date, _) in enumerate(DATES, 1):
            valeurs = {"id": "CTR-9%03d" % numero, "equipement_id": "EQ-0018", "nature": "Essai", "periodicite_mois": "12",
                       "derniere_date": date, "observations": "fuite %d" % numero, "observations_levees": "0"}
            ajout.append(";".join(valeurs.get(colonne, "") for colonne in colonnes))
        self.assertTrue(octets.endswith(CRLF))
        chemin.write_bytes(octets + "".join(ligne + "\r\n" for ligne in ajout).encode("utf-8"))
        return dossier

    def dates_reprises(self, octets):
        entete, *lignes = [ligne for ligne in lignes_csv(octets)]
        controle, date = entete.index("controle_id"), entete.index("date_controle")
        return {ligne[controle]: ligne[date] for ligne in lignes if ligne[controle].startswith("CTR-9")}

    def test_serveur_et_navigateur_protegent_la_date_et_ecrivent_les_memes_octets(self):
        base = self.base()
        attendues = {"CTR-9%03d" % numero: cellule for numero, (_, cellule) in enumerate(DATES, 1)}

        # Serveur : passage 3 → 4 au démarrage.
        with ServeurPrevo(source=base) as serveur:
            reserves = (serveur.dossier / "reserves_controle.csv").read_bytes()
            self.assertEqual(self.dates_reprises(reserves), attendues)
            # Le navigateur renvoie la table entière à chaque écriture : le serveur doit l'accepter.
            version = hashlib.sha256(reserves).hexdigest()[:16]
            statut, reponse = requete(serveur, "PUT", "/api/csv/reserves_controle", reserves,
                                      {"X-Version-Attendue": version, "Content-Type": "text/csv; charset=utf-8"})
            self.assertEqual(statut, 200, reponse)
            du_serveur = {chemin.name: chemin.read_bytes() for chemin in sorted(serveur.dossier.glob("*.csv"))}

        # Navigateur (Node) : la même base, par js/formats.js et js/donnees.js.
        node = shutil.which("node")
        if not node:
            self.skipTest("Node absent : miroir du navigateur non comparé")
        script = self.temporaire / "migrer.js"
        script.write_text(SCRIPT_NODE, encoding="utf-8")
        sortie = self.temporaire / "js"
        lance = subprocess.run([node, str(script), str(RACINE), str(base), str(sortie)], capture_output=True,
                               encoding="utf-8", timeout=120)
        self.assertEqual(lance.returncode, 0, lance.stderr[-2000:])
        resultat = json.loads(lance.stdout.strip().splitlines()[-1])
        self.assertIsNone(resultat["erreur"])
        self.assertEqual(resultat["format"], "4")
        # Relue par le navigateur, la date garde son apostrophe (un champ date n'est pas relu comme un texte) :
        # réécrite, la cellule reste protégée.
        self.assertEqual({controle: date for controle, date in resultat["dates"] if controle.startswith("CTR-9")},
                         attendues)
        du_navigateur = {chemin.name: chemin.read_bytes() for chemin in sorted(sortie.glob("*.csv"))}
        self.assertEqual(sorted(du_navigateur), sorted(du_serveur))
        # Hors comparaison : le journal (horodaté) et controles_reglementaires, dont le navigateur réécrit les dates
        # lisibles au format AAAA-MM-JJ (témoin 31/12/2025) quand le serveur garde chaque cellule telle quelle.
        for nom in du_serveur:
            if nom not in ("journal.csv", "controles_reglementaires.csv"):
                self.assertEqual(du_navigateur[nom], du_serveur[nom], nom + " : écart entre les deux miroirs")


class TestTesterUneSauvegardeAbimee(CasTemporaire):

    def sauvegarder_et_tester(self, serveur, abimer):
        """Abîme fournisseurs.csv dans les données, sauvegarde, teste → (manifeste, résultat du test)."""
        chemin = serveur.dossier / "fournisseurs.csv"
        sain = chemin.read_bytes()
        chemin.write_bytes(abimer(sain))
        statut, reponse = requete(serveur, "POST", "/api/sauvegarde")
        self.assertEqual(statut, 200, reponse)
        nom = reponse["sauvegarde"]
        manifeste = json.loads((serveur.dossier / "sauvegardes" / nom / "manifeste.json").read_text("utf-8-sig"))
        statut, resultat = requete(serveur, "POST", "/api/sauvegarde/tester", {"nom": nom})
        self.assertEqual(statut, 200, resultat)
        chemin.write_bytes(sain)
        return manifeste, resultat

    def verifier(self, manifeste, resultat, raison):
        self.assertEqual([decrit["nom"] for decrit in manifeste["fichiers"] if decrit.get("abime")],
                         ["fournisseurs.csv"])
        par_table = {table["table"]: table for table in resultat["tables"]}
        self.assertFalse(resultat["ok"], par_table["fournisseurs"])
        erreur = par_table["fournisseurs"]["erreur"]
        self.assertIsNotNone(erreur)
        self.assertIn("abîmé", erreur)
        self.assertIn(raison, erreur)
        self.assertEqual(par_table["fournisseurs"]["erreur_code"], "sauvegardes.test_abime")
        self.assertEqual([table["table"] for table in resultat["tables"] if table["erreur"]], ["fournisseurs"])

    def test_guillemet_jamais_ferme(self):
        def abimer(octets):
            entete, premiere, reste = octets.split(CRLF, 2)
            self.assertGreaterEqual(reste.count(CRLF), 3)
            return entete + CRLF + premiere + CRLF + b'"' + reste          # guillemet ouvert à la 2e ligne de données
        with ServeurPrevo() as serveur:
            manifeste, resultat = self.sauvegarder_et_tester(serveur, abimer)
            self.verifier(manifeste, resultat, "guillemet non fermé")

    def test_valeurs_au_dela_de_l_entete(self):
        def abimer(octets):
            largeur = octets.split(CRLF, 1)[0].count(b";") + 1
            return octets + ("X" + ";" * largeur + "en trop").encode("utf-8") + CRLF
        with ServeurPrevo() as serveur:
            manifeste, resultat = self.sauvegarder_et_tester(serveur, abimer)
            self.verifier(manifeste, resultat, "au-delà de l'en-tête")

    def test_temoin_sauvegarde_saine(self):
        with ServeurPrevo() as serveur:
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde")
            self.assertEqual(statut, 200, reponse)
            statut, resultat = requete(serveur, "POST", "/api/sauvegarde/tester", {"nom": reponse["sauvegarde"]})
            self.assertEqual(statut, 200, resultat)
            self.assertTrue(resultat["ok"])
            self.assertEqual({table["erreur"] for table in resultat["tables"]}, {None})


if __name__ == "__main__":
    unittest.main()
