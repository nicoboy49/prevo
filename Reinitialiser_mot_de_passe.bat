@echo off
rem ======================================================================
rem  Reinitialiser_mot_de_passe.bat - donne un mot de passe provisoire à un compte de Prévo.
rem  À lancer sur le PC serveur, celui où Prévo est installé : qui a la main sur ce PC a la main
rem  sur Prévo. Le mot de passe provisoire s'affiche une seule fois et devra être changé à la
rem  première connexion. Aucun courriel n'est envoyé (lot 7, ARCHITECTURE.md §22.3).
rem ======================================================================

chcp 65001 >nul
title Prévo - mot de passe oublié
cd /d "%~dp0"

rem Le même Python que Lancer_GMAO.bat : celui livré avec Prévo, sinon un Python installé (3.11 ou plus).
set "PYTHON="
if exist "%~dp0python\python.exe" (
    set "PYTHON="%~dp0python\python.exe""
    goto demander
)
call py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if defined PYTHON goto demander
call python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "PYTHON=python"
if defined PYTHON goto demander
echo  Python 3.11 ou plus récent est introuvable : lancez d'abord Lancer_GMAO.bat.
pause
exit /b 1

:demander
echo.
echo  Identifiant du compte (par exemple : nicolas.briand). Il est affiché dans Équipe, Accès.
set "IDENTIFIANT="
set /p "IDENTIFIANT= Identifiant : "
if not defined IDENTIFIANT (
    echo  Aucun identifiant saisi : rien n'a changé.
    pause
    exit /b 1
)
echo.
%PYTHON% serveur.py --reinitialiser "%IDENTIFIANT%"
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
