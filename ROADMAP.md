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

### 4.1 Labor-Import — Futtermittelanalyse aus CSV/Excel

#### Ziel
Analyseergebnisse akkreditierter Futtermittellabore (LUFA, AGES, SGS, Eurofins …)
direkt als neues Futtermittel importieren — ohne manuelle Abtippen-Fehler.

#### Unterstützte Quellformate

| Format | Beschreibung |
|---|---|
| CSV (Semikolon/Komma) | Generischer Rohdaten-Export der meisten Labore |
| XLSX | Excel-Analysebericht (häufig von LUFA Nord-West, AGES Wien) |
| PDF (Fallback) | Vorhandenes OCR-Modul (`ocr_import.py`) als Rückfall wenn kein strukturierter Export |

#### Importierbare Felder (Mapping → `futtermittel`-Tabelle)

| Labor-Bezeichnung (Beispiele) | DB-Feld | Einheit |
|---|---|---|
| Trockensubstanz / TS / DM | `wassergehalt_pct` (= 100 − TS) | % |
| Metabolisierbare Energie / ME | `energie_mj_me` | MJ/kg TS |
| Rohprotein / XP / Crude Protein | `rohprotein_pct` | % TS |
| Lysin | `lysin_g` | g/kg TS |
| Rohfett / XL | `rohfett_pct` | % TS |
| Rohfaser / XF | `rohfaser_pct` | % TS |
| Stärke / Starch | `staerke_pct` | % TS |
| Zucker / Zucker gesamt / ESC+WSC | `zucker_pct` | % TS |
| Calcium / Ca | `calcium_g` | g/kg TS |
| Phosphor / P | `phosphor_g` | g/kg TS |
| Magnesium / Mg | `magnesium_g` | g/kg TS |
| Natrium / Na | `natrium_g` | g/kg TS |
| Kalium / K | `kalium_g` | g/kg TS |
| Eisen / Fe | `eisen_mg` | mg/kg TS |
| Kupfer / Cu | `kupfer_mg` | mg/kg TS |
| Zink / Zn | `zink_mg` | mg/kg TS |
| Mangan / Mn | `mangan_mg` | mg/kg TS |
| Selen / Se | `selen_mg` | mg/kg TS |
| Jod / I | `jod_mg` | mg/kg TS |
| Vitamin E / α-Tocopherol | `vit_e_mg` | mg/kg TS |

#### Architektur

```
labor_import.py              ← neues Modul
  parse_csv(pfad) → dict
  parse_xlsx(pfad) → dict
  normalisiere_felder(roh) → dict   ← Alias-Mapping + Einheiten-Umrechnung
  validiere(daten) → list[str]      ← Warnungen bei unplausiblen Werten
  als_futtermittel(daten) → dict    ← bereit für database.speichere_futtermittel()

views/labor_import_view.py   ← Dialog (QDialog)
  Schritt 1: Datei auswählen (CSV/XLSX/PDF)
  Schritt 2: Vorschau-Tabelle — gemappte Felder + nicht erkannte Zeilen
  Schritt 3: Fehlende Felder manuell ergänzen
  Schritt 4: Name / Kategorie / Quelle bestätigen → Speichern
```

#### Normalisierungs-Logik (`normalisiere_felder`)

1. **Alias-Dictionary** — bekannte Laborbezeichnungen → DB-Feldname  
   (erweiterbar per JSON-Konfigurationsdatei `labor_aliase.json`)
2. **Einheiten-Erkennung** — automatische Umrechnung:
   - `% FM → % TS` anhand der TS-Angabe
   - `g/kg FM → g/kg TS`
   - `mg/kg FM → mg/kg TS`
3. **ME-Schätzung** falls nicht angegeben:  
   `ME ≈ 0.95 × (Rohprotein×0.134 + Rohfett×0.200 + NfE×0.143 + Rohfaser×0.076)`  
   (GfE-Schätzgleichung für Pferde, als Hinweis markiert)

#### Validierungsregeln (Plausibilitätsprüfung)

| Feld | Untergrenze | Obergrenze | Warnung |
|---|---|---|---|
| `energie_mj_me` | 3.0 | 16.0 | MJ/kg TS außerhalb Normalbereich |
| `rohprotein_pct` | 2.0 | 40.0 | — |
| `calcium_g` | 0.1 | 30.0 | — |
| `selen_mg` | 0.01 | 2.0 | Selen-Toxizitätsrisiko bei > 2 mg/kg TS |
| `wassergehalt_pct` | 5.0 | 80.0 | — |
| Ca:P-Verhältnis | 1.0 | 6.0 | Umgekehrtes Verhältnis kritisch |

Validierungsfehler → orange hervorgehobene Zeilen in der Vorschau,  
kein Abbruch — Benutzer entscheidet selbst.

#### Erweiterungspunkt: `labor_aliase.json`

```json
{
  "Trockensubstanz": "wassergehalt_pct",
  "TS": "wassergehalt_pct",
  "Dry Matter": "wassergehalt_pct",
  "ME Pferd": "energie_mj_me",
  "XP": "rohprotein_pct",
  "Crude Protein": "rohprotein_pct",
  "WSC+ESC": "zucker_pct"
}
```

Datei liegt neben der `.exe` → Labore mit abweichenden Spaltenköpfen  
können ohne Code-Änderung ergänzt werden.

#### Abhängigkeiten

| Paket | Verwendung |
|---|---|
| `openpyxl` | bereits installiert (XLSX-Export) — für XLSX-Import wiederverwenden |
| `csv` | stdlib, kein Zusatzpaket |
| `reportlab` / `ocr_import.py` | PDF-Fallback (optional, nur wenn reportlab+easyocr vorhanden) |

---

### 4.2 OCR-Import ausbauen

Vorhandenes `ocr_import.py` (EasyOCR + OpenCV) zum vollwertigen Import-Pfad ausbauen:
- Erkannte Felder direkt in den Labor-Import-Dialog (4.1) übergeben
- Qualitätsscore je Feld anzeigen (OCR-Konfidenz)
- Manuelle Korrektur unsicherer Werte vor dem Speichern

---

### 4.3 Futtermittel-Datenbank-Update (Online-Feed)

- [ ] JSON-Endpunkt (GitHub Releases oder eigener Server) mit geprüften Stammdaten
- [ ] Beim Start prüfen ob neuere Futtermittel-Stammdaten verfügbar → optionaler Download
- [ ] Nur additive Updates — bestehende Benutzerdaten werden nie überschrieben

---

### 4.4 Mehrsprachigkeit

- [ ] Qt Linguist / `.ts`-Dateien für DE / EN
- [ ] Sprachauswahl in den Einstellungen

---

### 4.5 Cloud-Sync / Backup

- [ ] Konfigurierbarer Backup-Pfad (OneDrive, NAS, USB)
- [ ] Automatisches tägliches Backup beim Programmstart

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
