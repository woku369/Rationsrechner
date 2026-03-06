@echo off
REM Gurktaler Pferdefutter-Rationsrechner - Startet die Anwendung
REM Hinweis: Fuer Doppelklick-Start bitte "Rationsrechner starten.vbs" verwenden!

SET VIRTUAL_ENV=
SET VIRTUAL_ENV_PROMPT=
SET PYTHONHOME=
SET PYTHONPATH=

REM pushd auf lokales Verzeichnis verhindert UNC-CWD-Fehler
pushd "%USERPROFILE%"

C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe "\\100.121.103.107\Gurktaler Daten\Rationsrechner\main.py"

popd
