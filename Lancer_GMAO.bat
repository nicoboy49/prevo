@echo off
rem ======================================================================
rem  Lancer_GMAO.bat - démarre la GMAO « Prévo » par un double-clic.
rem  Ce fichier cherche Python, puis lance le petit serveur local
rem  (serveur.py) qui ouvre lui-même le navigateur.
rem  Les lignes affichées ici, avant Python, sont en français puis en anglais
rem  (T297) : la langue de l'installation n'est connue que de serveur.py, qui
rem  écrit ensuite sa console dans cette langue.
rem ======================================================================

rem Affichage correct des accents dans la fenêtre noire.
chcp 65001 >nul
rem Titre de la fenêtre.
title Prévo — GMAO
rem Se placer dans le dossier où se trouve ce fichier.
cd /d "%~dp0"

rem ----- Étape 1 : le Python livré avec Prévo (zip de la release, dossier python\), sinon un Python installé -----
set "PYTHON="
set "TROP_ANCIEN="
if exist "%~dp0python\python.exe" (
    set "PYTHON="%~dp0python\python.exe""
    goto lancer
)
rem Un Python installé n'est accepté que si « import sys; sys.exit(version < 3.11) » renvoie 0.
rem Cela écarte aussi le faux « python » du Microsoft Store (il renvoie un code non nul).
rem « call » permet d'appeler aussi bien un .exe qu'un .cmd sans quitter ce fichier.
rem Premier essai : le lanceur « py » installé avec Python sous Windows.
call py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if not defined PYTHON (
    call py -3 --version >nul 2>&1
    if not errorlevel 1 set "TROP_ANCIEN=1"
)
if defined PYTHON goto lancer
rem Second essai : la commande « python ».
call python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYTHON=python"
if not defined PYTHON (
    call python --version >nul 2>&1
    if not errorlevel 1 set "TROP_ANCIEN=1"
)
if defined PYTHON goto lancer

rem ----- Étape 2 : Python est absent, on explique et on propose de l'installer -----
echo.
if defined TROP_ANCIEN (
    echo  Le Python présent sur cet ordinateur est trop ancien : la GMAO Prévo demande Python 3.11 ou plus récent.
    echo  Installez une version récente depuis https://www.python.org/downloads/ puis relancez ce fichier.
    echo  The Python on this computer is too old: Prévo needs Python 3.11 or later.
    echo  Install a recent version from https://www.python.org/downloads/ then run this file again.
) else (
    echo  Python n'est pas installé sur cet ordinateur.
    echo  Python is not installed on this computer.
)
echo  La GMAO Prévo en a besoin pour fonctionner (gratuit, officiel).
echo  Prévo needs it to run (free, official).
echo.
rem Winget est l'installateur intégré à Windows 10/11 : est-il disponible ?
call winget --version >nul 2>&1
if errorlevel 1 goto manuel
echo  Je peux installer Python 3.14 automatiquement avec winget.
echo  I can install Python 3.14 automatically with winget.
choice /C ON /M "Installer Python maintenant / Install Python now (O = Oui/Yes, N = Non/No)"
rem choice renvoie 1 pour O et 2 pour N.
if errorlevel 2 goto manuel
call winget install -e --id Python.Python.3.14 --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto manuel
echo.
echo  Python est installé. Fermez cette fenêtre puis relancez Lancer_GMAO.bat
echo  (la fenêtre actuelle ne connaît pas encore le nouveau Python).
echo  Python is installed. Close this window then run Lancer_GMAO.bat again
echo  (this window does not know the new Python yet).
pause
exit /b 0

:manuel
rem Installation manuelle : winget absent, refusé ou en échec.
echo.
echo  Installez Python vous-même depuis : https://www.python.org/downloads/
echo  Pendant l'installation, cochez la case « Add python.exe to PATH ».
echo  Ensuite, relancez Lancer_GMAO.bat.
echo  Install Python yourself from: https://www.python.org/downloads/
echo  During the installation, tick "Add python.exe to PATH".
echo  Then run Lancer_GMAO.bat again.
echo.
pause
exit /b 1

:lancer
rem ----- Étape 3 : rappel pare-feu -----
echo  Au premier lancement, Windows peut demander d'autoriser Python dans le pare-feu : choisissez le réseau privé.
echo  On the first start, Windows may ask to allow Python through the firewall: choose the private network.
echo.

rem ----- Étape 4 : lancer le serveur (les options reçues sont transmises) -----
rem Pour arrêter la GMAO : fermez cette fenêtre ou appuyez sur Ctrl+C.
%PYTHON% serveur.py %*

rem ----- Étape 5 : en cas d'erreur, laisser le temps de lire le message -----
if errorlevel 1 (
    echo.
    echo  Le serveur s'est arrêté avec une erreur. Lisez le message ci-dessus.
    echo  The server stopped with an error. Read the message above.
    pause
)
