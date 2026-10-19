"""Pilotage du vrai Microsoft Excel pour les tests CSV de Prévo (ARCHITECTURE.md §3).

Deux fonctions :
    excel_disponible()                      vrai si Excel peut être piloté sur ce poste
    aller_retour_excel(source, sortie, format='utf8', modifications=None)
        ouvre `source` dans Excel comme un utilisateur (double-clic, réglages régionaux du poste),
        applique d'éventuelles saisies, puis « Enregistrer sous » CSV dans `sortie`.

Pourquoi VBScript : sur ce poste, l'automatisation COM d'Excel depuis PowerShell échoue
(0x80040155 « Interface non enregistrée ») alors que VBScript (cscript) fonctionne. Le script
.vbs est écrit dans un dossier temporaire, lancé par `cscript //nologo`, puis supprimé.
Le script ne contient que des caractères ASCII : les autres caractères passent par ChrW(n).

Bibliothèque standard seulement. Utilisé par tests/test_csv.py.
"""
import functools
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Formats de « Enregistrer sous » (XlFileFormat)
FORMATS_EXCEL = {
    "utf8": 62,   # xlCSVUTF8 : « CSV UTF-8 (délimité par des virgules) »
    "ansi": 6,    # xlCSV     : « CSV (délimité par des virgules) », Windows-1252 sans BOM
}

DELAI_EXCEL_S = 180


def chaine_vbs(texte):
    """Expression VBScript qui vaut exactement `texte`.

    Les caractères ASCII imprimables sont écrits tels quels (guillemet doublé), les autres
    (accents, guillemets français, sauts de ligne…) par ChrW(code).
    Exemple : « été » donne  ChrW(233) & "t" & ChrW(233)
    """
    morceaux = []
    courant = ""
    for caractere in texte:
        code = ord(caractere)
        if 32 <= code < 127:
            courant += '""' if caractere == '"' else caractere
            continue
        if courant:
            morceaux.append('"' + courant + '"')
            courant = ""
        if code > 0xFFFF:  # hors plan de base : paire de substitution UTF-16
            code -= 0x10000
            morceaux.append("ChrW(%d)" % (0xD800 + (code >> 10)))
            morceaux.append("ChrW(%d)" % (0xDC00 + (code & 0x3FF)))
        else:
            morceaux.append("ChrW(%d)" % code)
    if courant or not morceaux:
        morceaux.append('"' + courant + '"')
    return " & ".join(morceaux)


# Squelette commun : Excel invisible, aucune question, fermeture d'Excel même en cas d'erreur.
# {corps} est remplacé par les instructions propres à chaque usage.
MODELE_VBS = """Option Explicit
Dim xl, wb, etape
On Error Resume Next
etape = "demarrage d'Excel"
Set xl = CreateObject("Excel.Application")
Verifier
xl.Visible = False
xl.DisplayAlerts = False
{corps}
If IsObject(wb) Then wb.Close False
xl.Quit
WScript.Echo "OK"
WScript.Quit 0

Sub Verifier()
  If Err.Number <> 0 Then
    WScript.Echo "ERREUR pendant : " & etape & " (" & Err.Number & ") " & Err.Description
    Err.Clear
    If IsObject(wb) Then wb.Close False
    If IsObject(xl) Then xl.Quit
    WScript.Quit 1
  End If
End Sub
"""


def _executer_vbs(corps):
    """Écrit le script dans un dossier temporaire, le lance par cscript et le supprime.

    Renvoie (code_retour, sortie_console). Lève subprocess.TimeoutExpired si Excel ne répond pas.
    """
    dossier = Path(tempfile.mkdtemp(prefix="prevo-excel-"))
    try:
        script = dossier / "excel.vbs"
        script.write_text(MODELE_VBS.replace("{corps}", corps), encoding="ascii", newline="\r\n")
        resultat = subprocess.run(
            ["cscript", "//nologo", str(script)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=DELAI_EXCEL_S)
        sortie = resultat.stdout.decode("oem" if os.name == "nt" else "latin-1", errors="replace")
        return resultat.returncode, sortie.strip()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


@functools.lru_cache(maxsize=1)
def excel_disponible():
    """Vrai si Microsoft Excel peut être lancé par VBScript sur ce poste (résultat mémorisé)."""
    if os.name != "nt" or shutil.which("cscript") is None:
        return False
    try:
        code, sortie = _executer_vbs("")
    except (OSError, subprocess.SubprocessError):
        return False
    return code == 0 and sortie.endswith("OK")


def version_excel():
    """Numéro de version d'Excel (ex. « 16.0 »), ou None si Excel n'est pas disponible."""
    if not excel_disponible():
        return None
    code, sortie = _executer_vbs("WScript.Echo xl.Version")
    lignes = sortie.splitlines()
    return lignes[0].strip() if code == 0 and len(lignes) >= 2 else None


def aller_retour_excel(source, sortie, format="utf8", modifications=None):
    """Ouvre `source` dans le vrai Excel puis l'enregistre en CSV dans `sortie`.

    - Ouverture : Workbooks.Open(chemin, …, Local:=True), comme un double-clic sur un poste
      fr-FR (séparateur « ; », dates JJ/MM/AAAA).
    - modifications : liste de (ligne, colonne, valeur), numérotées à partir de 1 comme dans
      Excel ; chaque valeur est posée par Cells(ligne, colonne).Value = « texte », ce qui équivaut
      à une saisie au clavier (Excel interprète les dates et les nombres).
    - Enregistrement : SaveAs chemin, 62 (CSV UTF-8) ou 6 (CSV, Windows-1252), Local:=True.
    Excel travaille sur des copies dans un dossier temporaire ; `sortie` est écrasé.
    Lève RuntimeError (avec la sortie de cscript) en cas d'échec.
    """
    if format not in FORMATS_EXCEL:
        raise ValueError("format inconnu : %r (attendu : %s)" % (format, ", ".join(FORMATS_EXCEL)))
    source = Path(source).resolve()
    sortie = Path(sortie).resolve()
    dossier = Path(tempfile.mkdtemp(prefix="prevo-excel-fichiers-"))
    try:
        entree_excel = dossier / "entree.csv"
        sortie_excel = dossier / "sortie.csv"
        shutil.copyfile(str(source), str(entree_excel))

        lignes = [
            'etape = "ouverture du fichier"',
            "Set wb = xl.Workbooks.Open(%s, , , , , , , , , , , , , True)" % chaine_vbs(str(entree_excel)),
            "Verifier",
        ]
        for ligne, colonne, valeur in modifications or []:
            lignes.append('etape = "saisie en ligne %d, colonne %d"' % (int(ligne), int(colonne)))
            lignes.append("wb.Worksheets(1).Cells(%d, %d).Value = %s" % (int(ligne), int(colonne), chaine_vbs(valeur)))
            lignes.append("Verifier")
        lignes += [
            'etape = "enregistrement"',
            "wb.SaveAs %s, %d, , , , , , , , , , True" % (chaine_vbs(str(sortie_excel)), FORMATS_EXCEL[format]),
            "Verifier",
        ]
        code, console = _executer_vbs("\r\n".join(lignes))
        if code != 0 or not sortie_excel.is_file():
            raise RuntimeError("Excel n'a pas pu faire l'aller-retour (code %s) : %s" % (code, console))
        sortie.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(sortie_excel), str(sortie))
        return sortie
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
