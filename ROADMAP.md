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

### 4.1 Blutbild-Import (Laboklin / IDEXX)

#### Ziel
Tierärztliche Blutbefunde direkt einlesen und automatisch mit dem ernährungsphysiologischen
Versorgungszustand des Pferdes verknüpfen. Mangelzustände oder Überversorgungen werden
erkannt und der **Optimierungsassistent** reagiert mit konkreten Fütterungsanpassungen.

#### Unterstützte Labor-Quellen (Phase 1)

| Labor | Export-Format | Erkennungsmerkmal |
|---|---|---|
| **Laboklin** (Bad Kissingen) | PDF-Befundbericht | Kopfzeile „LABOKLIN", Tabelle mit Analyt / Ergebnis / Referenz |
| **IDEXX Laboratories** | PDF + optional CSV | Kopfzeile „IDEXX", ähnliche Tabellenstruktur |
| Generisch | CSV (Semikolon) | Spalten: Analyt, Wert, Einheit, Referenz_min, Referenz_max |

#### Relevante Blutparameter für die Fütterungsberatung

| Blutparameter | Einheit | Bezug zur Fütterung |
|---|---|---|
| Selen (Se, Vollblut) | µg/l | Direkt → `selen_mg` Bedarf; enge therapeutische Breite |
| Glutathionperoxidase (GPX) | U/gHb | Indirekter Se-Status; sensitiver als Serum-Se |
| Kupfer (Cu, Serum) | µmol/l | → `kupfer_mg`; Antagonismus mit Zink/Eisen/Molybdän |
| Zink (Zn, Serum) | µmol/l | → `zink_mg`; Wechselwirkung Kupfer |
| Eisen (Fe, Serum) | µmol/l | → `eisen_mg`; Eisenüberschuss hemmt Cu-Resorption |
| Magnesium (Mg, Serum) | mmol/l | → `magnesium_g`; relevant bei EMS/PPID |
| Calcium (Ca, Serum) | mmol/l | → `calcium_g`; im Kontext Trächtigkeit/Laktation |
| Vitamin E (α-Tocopherol) | µmol/l | → `vit_e_mg`; Oxidativer Stress, Muskelgesundheit |
| Vitamin A (Retinol) | µmol/l | → `vit_a_ie`; bei Weidemangel oder Lagerungsheu |
| Schilddrüse T3/T4 | nmol/l | Hinweis auf Jodversorgung (indirekt) |
| ACTH | pg/ml | PPID-Screening → Diagnose „Cushing" vorschlagen |
| Insulin (basales Insulin) | µU/ml | EMS-Marker → Diagnoseflag setzen |

#### Referenzbereiche

Laboklin/IDEXX liefern eigene Referenzen im Bericht mit.
Die App nutzt diese **laboreigenen Referenzen** als primäre Quelle.
Fallback: integrierte GfE/eigene Normwerte in `blutbild_referenz.json`.

```json
{
  "selen_vollblut_ug_l":    { "min": 120, "max": 250, "einheit": "µg/l" },
  "kupfer_serum_umol_l":    { "min": 12,  "max": 22,  "einheit": "µmol/l" },
  "zink_serum_umol_l":      { "min": 10,  "max": 18,  "einheit": "µmol/l" },
  "vit_e_umol_l":           { "min": 4.0, "max": 20.0, "einheit": "µmol/l" },
  "magnesium_serum_mmol_l": { "min": 0.7, "max": 1.1,  "einheit": "mmol/l" }
}
```

#### Bewertungslogik: Blut → Versorgungszustand

```
Wert < Referenz_min × 0.85  → "Mangel"       (rot)
Wert < Referenz_min         → "Grenzwertig"   (orange)
Referenz_min ≤ Wert ≤ max   → "Optimal"       (grün)
Wert > Referenz_max × 1.15  → "Überversorgung" (lila)
```

Sonderregel **Selen**: Toleranzbereich besonders eng —
`> 300 µg/l` Vollblut → Toxizitätswarnung, Supplement-Empfehlung blockiert.

#### Verknüpfung mit dem Optimierungsassistenten

Blutbefunde werden als **pferdespezifische Constraints** gespeichert und beim nächsten
Aufruf des Optimierungsassistenten automatisch eingeblendet:

```
blutbefund_status = {
  "selen":   "Mangel",       → Supplement-Vorschlag: Selenomethionin
  "kupfer":  "Optimal",      → kein Eingriff
  "vit_e":   "Grenzwertig",  → Hinweis: Vitamin-E-Supplement erwägen
  "insulin": 45,             → Flag EMS automatisch setzen (wenn > 40 µU/ml)
  "acth":    112,            → Flag Cushing vorschlagen (wenn > 80 pg/ml saisonal adj.)
}
```

Der Optimierungsassistent priorisiert Supplemente, die einen dokumentierten
Mangel beheben — und sperrt Supplemente, die eine Überversorgung verschlechtern würden.

#### Architektur

```
blutbild_import.py                  ← neues Modul
  erkenne_labor(pfad) → "laboklin" | "idexx" | "generisch"
  parse_laboklin_pdf(pfad) → list[BlutWert]
  parse_idexx_pdf(pfad) → list[BlutWert]
  parse_csv(pfad) → list[BlutWert]
  bewerte(werte, referenzen) → list[BlutBewertung]
  als_pferd_constraints(bewertungen) → dict   ← für Optimierungsassistent

@dataclass
class BlutWert:
    analyt: str          # z.B. "Selen"
    wert: float
    einheit: str
    ref_min: float | None
    ref_max: float | None
    datum: str

@dataclass
class BlutBewertung:
    blut_wert: BlutWert
    status: str          # "Mangel" | "Grenzwertig" | "Optimal" | "Überversorgung"
    db_feld: str | None  # Zugeordnetes Nährstofffeld, z.B. "selen_mg"
    empfehlung: str      # Freitext-Hinweis

views/blutbild_view.py              ← neuer Tab / Dialog
  Schritt 1: PDF oder CSV auswählen
  Schritt 2: Erkannte Werte + Ampelfarben anzeigen
  Schritt 3: Datum + Tierarzt/Labor speichern
  Schritt 4: "Optimierungsassistent öffnen" → Constraints übernehmen
```

#### Datenbank-Erweiterung

```sql
CREATE TABLE IF NOT EXISTS blutbefunde (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pferd_id     INTEGER NOT NULL REFERENCES pferde(id) ON DELETE CASCADE,
    datum        TEXT NOT NULL,
    labor        TEXT,          -- Laboklin | IDEXX | Sonstige
    tierarzt     TEXT,
    erstellt_am  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS blutbefund_werte (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    befund_id       INTEGER NOT NULL REFERENCES blutbefunde(id) ON DELETE CASCADE,
    analyt          TEXT NOT NULL,
    wert            REAL NOT NULL,
    einheit         TEXT,
    ref_min         REAL,
    ref_max         REAL,
    status          TEXT,       -- Mangel | Grenzwertig | Optimal | Überversorgung
    db_feld         TEXT        -- Mapping zu Nährstoff-Feld
);
```

#### Verlaufsansicht

Mehrere Befunde desselben Pferdes → Trendanzeige:
- Selen-Verlauf über 12 Monate nach Supplementierung
- Visueller Nachweis der Fütterungswirksamkeit

#### Abhängigkeiten

| Paket | Verwendung |
|---|---|
| `pdfplumber` oder `pymupdf` | PDF-Tabellen strukturiert auslesen (besser als OCR) |
| `csv` | stdlib |
| `reportlab` | bereits vorhanden — für Befund-Export-PDF |

> **Hinweis zu `pdfplumber` vs. OCR:** Laboklin/IDEXX-PDFs sind
> maschinenlesbare PDFs (kein Scan) → `pdfplumber` extrahiert Tabellen
> direkt ohne OCR-Fehler. OCR (`ocr_import.py`) nur als Fallback bei
> eingescannten Altbefunden.

---

### 4.2 Futtermittelanalyse-Import (LUFA / AGES / Eurofins)

Analyseergebnisse akkreditierter Futtermittellabore direkt als neues Futtermittel importieren.

#### Unterstützte Formate: CSV, XLSX, PDF (OCR-Fallback)

#### Importierbare Felder (Mapping → `futtermittel`-Tabelle)

| Labor-Bezeichnung | DB-Feld | Einheit |
|---|---|---|
| Trockensubstanz / TS / DM | `wassergehalt_pct` (= 100 − TS) | % |
| Metabolisierbare Energie / ME | `energie_mj_me` | MJ/kg TS |
| Rohprotein / XP | `rohprotein_pct` | % TS |
| Rohfaser / XF | `rohfaser_pct` | % TS |
| Stärke / Starch | `staerke_pct` | % TS |
| Zucker / ESC+WSC | `zucker_pct` | % TS |
| Calcium / Ca | `calcium_g` | g/kg TS |
| Phosphor / P | `phosphor_g` | g/kg TS |
| Kupfer / Cu | `kupfer_mg` | mg/kg TS |
| Selen / Se | `selen_mg` | mg/kg TS |
| … (alle Felder analog zu 4.1) | | |

Alias-Mapping erweiterbar per `labor_aliase.json` (kein Code-Eingriff nötig).

#### Architektur: `labor_import.py` + `views/labor_import_view.py` (3-Schritt-Wizard)

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
