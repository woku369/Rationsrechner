@echo off
REM Gurktaler Pferdefutter-Rationsrechner
REM Launcher: Wechselt auf lokales Laufwerk, dann startet die App

SET APP_DIR=\\100.121.103.107\Gurktaler Daten\Rationsrechner
SET PYTHON=%APP_DIR%\.venv\Scripts\python.exe

REM VIRTUAL_ENV leeren - verhindert site.py Fehler bei UNC-Venv
SET VIRTUAL_ENV=
SET VIRTUAL_ENV_PROMPT=
SET PYTHONPATH=%APP_DIR%

REM In lokales Userprofile-Verzeichnis wechseln (UNC als CWD macht Python 3.13 Probleme)
cd /d "%USERPROFILE%"

"%PYTHON%" "%APP_DIR%\main.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo FEHLER beim Starten. Bitte Fehlermeldung oben pruefen.
    pause
)
