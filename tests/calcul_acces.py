"""Calcul indépendant des empreintes de mot de passe de Prévo (lot 7, ARCHITECTURE.md §22.3 ; CS121).

Recalcule, à partir des seuls paramètres écrits dans le contrat (et non du code de serveur.py), l'empreinte attendue
d'un mot de passe pour un compte de donnees/acces/comptes.json :
    scrypt-n15-r8-p3      hashlib.scrypt(mot de passe UTF-8, sel, n=32768, r=8, p=3, dklen=32)
    pbkdf2-sha256-600000  hashlib.pbkdf2_hmac('sha256', mot de passe UTF-8, sel, 600000, dklen=32)
Sel et empreinte sont en base64.
"""
import base64
import hashlib

PARAMETRES = {
    "scrypt-n15-r8-p3": ("scrypt", {"n": 32768, "r": 8, "p": 3}),
    "pbkdf2-sha256-600000": ("pbkdf2", {"iterations": 600000}),
}


def empreinte(algo, mot_de_passe, sel_base64):
    """Empreinte attendue (base64) pour cet algorithme, ce mot de passe et ce sel."""
    famille, reglages = PARAMETRES[algo]
    sel = base64.b64decode(sel_base64)
    octets = mot_de_passe.encode("utf-8")
    if famille == "scrypt":
        brut = hashlib.scrypt(octets, salt=sel, n=reglages["n"], r=reglages["r"], p=reglages["p"],
                              maxmem=128 * 1024 * 1024, dklen=32)
    else:
        brut = hashlib.pbkdf2_hmac("sha256", octets, sel, reglages["iterations"], dklen=32)
    return base64.b64encode(brut).decode("ascii")
