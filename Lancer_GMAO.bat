@echo off
rem ======================================================================
rem  Lancer_GMAO.bat - démarre la GMAO « Prévo » par un double-clic.
rem  Ce fichier cherche Python, puis lance le petit serveur local
rem  (serveur.py) qui ouvre lui-même le navigateur.
rem ======================================================================

rem Affichage correct des accents dans la fenêtre noire.
chcp 65001 >nul
rem Titre de la fenêtre.
title Prévo — GMAO
rem Se placer dans le dossier où se trouve ce fichier.
cd /d "%~dp0"

rem ----- Étape 1 : chercher Python sur l'ordinateur -----
set "PYTHON="
rem Premier essai : le lanceur « py » installé avec Python sous Windows.
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
rem Second essai : la commande « python » (testée, car Windows peut fournir
rem un faux « python » du Microsoft Store qui ne fait rien).
if not defined PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)
if defined PYTHON goto lancer

rem ----- Étape 2 : Python est absent, on explique et on propose de l'installer -----
echo.
echo  Python n'est pas installé sur cet ordinateur.
echo  La GMAO Prévo en a besoin pour fonctionner (gratuit, officiel).
echo.
rem Winget est l'installateur intégré à Windows 10/11 : est-il disponible ?
winget --version >nul 2>&1
if errorlevel 1 goto manuel
echo  Je peux installer Python 3.12 automatiquement avec winget.
choice /C ON /M "Installer Python maintenant (O = Oui, N = Non)"
rem choice renvoie 1 pour O et 2 pour N.
if errorlevel 2 goto manuel
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto manuel
echo.
echo  Python est installé. Fermez cette fenêtre puis relancez Lancer_GMAO.bat
echo  (la fenêtre actuelle ne connaît pas encore le nouveau Python).
pause
exit /b 0

:manuel
rem Installation manuelle : winget absent, refusé ou en échec.
echo.
echo  Installez Python vous-même depuis : https://www.python.org/downloads/
echo  Pendant l'installation, cochez la case « Add python.exe to PATH ».
echo  Ensuite, relancez Lancer_GMAO.bat.
echo.
pause
exit /b 1

:lancer
rem ----- Étape 3 : rappel pare-feu -----
echo  Au premier lancement, Windows peut demander d'autoriser Python dans le pare-feu : choisissez le réseau privé.
echo.

rem ----- Étape 4 : lancer le serveur (les options reçues sont transmises) -----
rem Pour arrêter la GMAO : fermez cette fenêtre ou appuyez sur Ctrl+C.
%PYTHON% serveur.py %*

rem ----- Étape 5 : en cas d'erreur, laisser le temps de lire le message -----
if errorlevel 1 (
    echo.
    echo  Le serveur s'est arrêté avec une erreur. Lisez le message ci-dessus.
    pause
)
