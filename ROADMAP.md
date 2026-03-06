# Gurktaler Pferdefutter-Rationsrechner — Roadmap

> Stand: März 2026  
> Repository: https://github.com/woku369/Rationsrechner

---

## Aktueller Stand (v0.3 — März 2026)

| Modul | Status |
|---|---|
| Kunden- & Pferde-Verwaltung | ✅ fertig |
| Futtermittel-Datenbank (CRUD) | ✅ fertig |
| Supplement-Katalog (CRUD, org. Formen) | ✅ fertig |
| Rationsberechnung (GfE 6. Aufl. 2014) | ✅ fertig |
| Bedarfsberechnung K1–K6 (Plausibilität) | ✅ fertig |
| Raufutter-Verlust & Mahlzeiten | ✅ fertig |
| Individueller Energie-Override pro Pferd | ✅ fertig |
| Optimierungsassistent (3-Varianten-Vergleich) | ✅ fertig |
| Export XLSX + PDF (inkl. Diff-%) | ✅ fertig |
| Erhebungsblatt PDF (Leerformular) | ✅ fertig |
| Eisen in allen Ausgaben | ✅ fertig |

---

## Phase 1 — Win64-Standalone-App (nächster Schritt)

### Ziel
Die Anwendung soll als **einzelne `.exe`-Datei** (oder portables Verzeichnis)
ohne Python-Installation auf jedem Windows-10/11-PC (64-Bit) lauffähig sein.

### Werkzeug: PyInstaller

```
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/icon.ico --name "Rationsrechner" main.py
```

#### Wichtige PyInstaller-Optionen

| Option | Bedeutung |
|---|---|
| `--onefile` | Alles in eine einzige `.exe` packen |
| `--windowed` | Kein schwarzes Konsolenfenster |
| `--icon` | Programm-Icon (`.ico`, 256×256) |
| `--add-data "views;views"` | `views/`-Paket explizit einbinden |
| `--add-data "rationsrechner.db;."` | Datenbank mitliefern (Seed-Daten) |
| `--hidden-import PyQt6.sip` | Manchmal nötig bei PyQt6 |

#### Bekannte Stolperstellen

1. **UNC-Pfad als CWD** — bereits in `main.py` abgefangen (`os.chdir` auf lokales Profil).  
   PyInstaller extrahiert die App nach `%TEMP%\_MEIXXXXX` — absoluter Pfad, kein Problem.

2. **Datenbankpfad** — `database.py` benutzt:
   ```python
   DB_PATH = Path(os.path.abspath(__file__)).parent / "rationsrechner.db"
   ```
   Im gebundenen Modus ist `__file__` der temporäre Extraktionspfad.  
   **Lösung:** DB-Pfad auf persistenten Benutzerordner umleiten:
   ```python
   import sys
   if getattr(sys, 'frozen', False):
       DB_PATH = Path(os.environ.get("APPDATA","")) / "Rationsrechner" / "rationsrechner.db"
   else:
       DB_PATH = Path(os.path.abspath(__file__)).parent / "rationsrechner.db"
   ```

3. **Seed-Daten vs. Benutzerdaten** — Die `.db` im Bundle enthält nur Stammdaten.  
   Beim ersten Start wird sie nach `APPDATA\Rationsrechner\` kopiert (sofern noch nicht vorhanden).

4. **reportlab & openpyxl** — werden von PyInstaller automatisch erkannt, solange sie im `venv` installiert sind.

5. **Qt-Plugins** — PyInstaller bündelt Qt-Plattform-DLLs automatisch mit; kein `platforms/qwindows.dll`-Fehler zu erwarten.

#### Empfohlener Build-Workflow

```bat
:: Im Projektverzeichnis (lokaler Pfad empfohlen wegen UNC-Einschränkungen):
xcopy /E /I "\\100.121.103.107\Gurktaler Daten\Rationsrechner" "C:\Build\Rationsrechner"
cd C:\Build\Rationsrechner
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller rationsrechner.spec   :: nach erstem manuellen Build
```

#### `rationsrechner.spec` (nach erstem Lauf anpassen)

```python
# rationsrechner.spec
a = Analysis(
    ['main.py'],
    pathex=['.'],
    datas=[
        ('views', 'views'),
        ('rationsrechner.db', '.'),
        ('assets', 'assets'),   # Icon, ggf. Logos
    ],
    hiddenimports=['PyQt6.sip'],
    ...
)
```

#### Installer (optional): NSIS oder Inno Setup

Für eine "echte" Installations-`.exe` mit Desktop-Verknüpfung:

```
Inno Setup → einzelne Input-`.exe` → Output: `Rationsrechner_Setup_v1.0.exe`
```

---

## Phase 2 — Qualität & Stabilität (Q2 2026)

- [ ] **requirements.txt** vervollständigen (`PyQt6`, `openpyxl`, `reportlab`, Versionen pinnen)
- [ ] **Automatische Tests** — `pytest` für Bedarfsberechnung (K1–K6 Regressionen)
- [ ] **Fehler-Logging** in `APPDATA\Rationsrechner\error.log` (statt stiller Ausnahmen)
- [ ] **Auto-Backup** der DB vor jedem Update auf neue Schema-Version
- [ ] **Icons & Branding** — Programm-Icon, Splash-Screen
- [ ] **Versionsnummer** im Titel / Über-Dialog

---

## Phase 3 — Fachliche Erweiterungen (Q3 2026)

- [ ] **Vitamin-D-Bedarf** (Stallhaltung vs. Weide, Sonnenexposition)
- [ ] **Vitamin B1 / Biotin** im Vergleich anzeigen
- [ ] **Methionin** im Vergleich anzeigen
- [ ] **Ca:P-Verhältnis** als eigene Kennzahl (Warnung wenn < 1,5:1 oder > 3:1)
- [ ] **Kalium** im Vergleich anzeigen (relevant bei EMS/PPID)
- [ ] **Weide-Assistent** — saisonale Fructan-/NSC-Schätzung aus Weidestunden
- [ ] **Anamnese-Verlauf** — Gewicht & Beurteilungszahl (BCS) über Zeit tracken
- [ ] **Fütterungsplan** druckbar (Wochenübersicht je Pferd)

---

## Phase 4 — Daten & Integration (Q4 2026 / 2027)

- [ ] **Labor-Import** — Futtermittelanalyse per CSV/Excel direkt importieren
- [ ] **OCR-Import** (vorhandenes `ocr_import.py` ausbauen) — PDF-Analyseberichte einlesen
- [ ] **Futtermittel-Datenbank-Update** über Online-Feed (JSON-Endpunkt, optional)
- [ ] **Mehrsprachigkeit** — Deutsch / Englisch (Qt Linguist / `.ts`-Dateien)
- [ ] **Cloud-Sync** (optional) — DB-Backup auf OneDrive / NAS per konfigurierbarem Pfad

---

## Phase 5 — Vertrieb & Wartung (2027+)

- [ ] **Automatische Updates** — Versionsprüfung gegen GitHub Releases API, Download-Hinweis
- [ ] **Lizenzmodell** prüfen — Open Source (GPL) oder proprietär
- [ ] **Installer signieren** (Code Signing Certificate) für Windows SmartScreen
- [ ] **64-Bit ARM** (Windows on ARM) — PyInstaller unterstützt `arm64` ab v6

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| GUI | PyQt6 (Qt 6.x) |
| Berechnung | Python 3.13, reine stdlib + eigene Module |
| Datenbank | SQLite 3 (via `sqlite3` stdlib) |
| Export | `openpyxl` (XLSX), `reportlab` (PDF) |
| Packaging | PyInstaller 6.x |
| Versionskontrolle | Git / GitHub |
| CI (geplant) | GitHub Actions (Build + Test) |
