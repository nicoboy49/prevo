"""Faux mkcert pour les tests du lot 7 (CS126) : mêmes arguments que le vrai, certificats de test fabriqués par openssl.

    faux_mkcert.py -install
    faux_mkcert.py -cert-file CERT -key-file CLE nom1 nom2 …

CAROOT (variable d'environnement) : dossier de l'autorité ; rootCA.pem et rootCA-key.pem y sont créés s'ils manquent.
Chaque lancement ajoute une ligne à CAROOT/lancements.txt (les tests comptent les exécutions). Ce faux sert aussi à
prouver qu'un binaire dont l'empreinte est fausse n'est jamais exécuté : aucune ligne n'est alors écrite.
"""
import ipaddress
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHEMINS_OPENSSL = [r"C:\Program Files\Git\usr\bin\openssl.exe", r"C:\Program Files\Git\mingw64\bin\openssl.exe"]


def openssl():
    trouve = shutil.which("openssl")
    if trouve:
        return trouve
    for chemin in CHEMINS_OPENSSL:
        if os.path.isfile(chemin):
            return chemin
    sys.exit("faux mkcert : openssl introuvable")


def lancer(*arguments):
    environnement = dict(os.environ, MSYS_NO_PATHCONV="1", MSYS2_ARG_CONV_EXCL="*")
    subprocess.run([openssl()] + list(arguments), check=True, capture_output=True, env=environnement, timeout=60)


def main(arguments):
    autorite = Path(os.environ.get("CAROOT") or sys.exit("faux mkcert : CAROOT manquant"))
    autorite.mkdir(parents=True, exist_ok=True)
    with open(autorite / "lancements.txt", "a", encoding="utf-8") as journal:
        journal.write(" ".join(arguments) + "\n")
    racine, cle_racine = autorite / "rootCA.pem", autorite / "rootCA-key.pem"
    if not racine.is_file():
        # Autorité comme celle de mkcert : keyCertSign en plus de CA:TRUE, SKI et AKI que « req -x509 » pose seul ;
        # la vérification stricte d'OpenSSL 3 (Python 3.13) l'exige (T161).
        lancer("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(cle_racine), "-out", str(racine),
               "-days", "2", "-subj", "/CN=Faux mkcert de test", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    if arguments == ["-install"]:
        return 0
    certificat = arguments[arguments.index("-cert-file") + 1]
    cle = arguments[arguments.index("-key-file") + 1]
    noms = [a for i, a in enumerate(arguments) if not a.startswith("-") and arguments[i - 1] not in ("-cert-file", "-key-file")]
    alternatifs = []
    for nom in noms:
        try:
            ipaddress.ip_address(nom)
            alternatifs.append("IP:" + nom)
        except ValueError:
            alternatifs.append("DNS:" + nom)
    with tempfile.TemporaryDirectory() as dossier:
        demande, extension = Path(dossier) / "demande.csr", Path(dossier) / "ext.cnf"
        # Mêmes extensions qu'un certificat de serveur de mkcert : sans l'identifiant de l'autorité, la vérification
        # stricte d'OpenSSL 3 (Python 3.13, ssl.create_default_context) refuse le certificat (T161).
        extension.write_text("subjectAltName=" + ",".join(alternatifs) + "\nbasicConstraints=CA:FALSE\n"
                             "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n"
                             "keyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n",
                             encoding="ascii")
        lancer("req", "-newkey", "rsa:2048", "-nodes", "-keyout", cle, "-out", str(demande), "-subj", "/CN=" + noms[0])
        lancer("x509", "-req", "-in", str(demande), "-CA", str(racine), "-CAkey", str(cle_racine), "-CAcreateserial",
               "-out", certificat, "-days", "2", "-extfile", str(extension))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
