' Gurktaler Pferdefutter-Rationsrechner - Launcher
' VBScript umgeht das UNC-Pfad-CWD-Problem von CMD.EXE

Dim oShell, sPython, sScript, sUserProfile

Set oShell = CreateObject("WScript.Shell")

' Lokales Benutzerverzeichnis als Arbeitsverzeichnis
sUserProfile = oShell.ExpandEnvironmentStrings("%USERPROFILE%")
oShell.CurrentDirectory = sUserProfile

' Umgebungsvariablen bereinigen (kein venv, kein PYTHONHOME)
oShell.Environment("Process")("VIRTUAL_ENV")      = ""
oShell.Environment("Process")("VIRTUAL_ENV_PROMPT") = ""
oShell.Environment("Process")("PYTHONHOME")       = ""
oShell.Environment("Process")("PYTHONPATH")        = ""

' Pfade
sPython  = "C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe"
sScript  = "\\100.121.103.107\Gurktaler Daten\Rationsrechner\main.py"

' App starten (1 = normales Fenster, False = nicht warten)
oShell.Run """" & sPython & """ """ & sScript & """", 1, False

Set oShell = Nothing
