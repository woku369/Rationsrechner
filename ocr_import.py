"""
OCR-Modul: Etikett-Foto per EasyOCR auslesen und Nährwerte extrahieren.
"""

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Bildvorverarbeitung mit OpenCV
# ---------------------------------------------------------------------------

def vorverarbeite_bild(bild_pfad: str) -> str:
    """
    Verbessert das Bild für bessere OCR-Erkennung.
    Gibt den Pfad zum verarbeiteten Bild zurück.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(bild_pfad)
        if img is None:
            return bild_pfad

        # Graustufen
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Kontrastverstärkung (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Schärfen
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        gray = cv2.filter2D(gray, -1, kernel)

        # Rauschen reduzieren
        gray = cv2.fastNlMeansDenoising(gray, h=10)

        # Speichern
        out_pfad = str(Path(bild_pfad).with_suffix(".verarbeitet.jpg"))
        cv2.imwrite(out_pfad, gray)
        return out_pfad

    except ImportError:
        return bild_pfad  # OpenCV nicht verfügbar, Original verwenden
    except Exception:
        return bild_pfad


# ---------------------------------------------------------------------------
# OCR mit EasyOCR
# ---------------------------------------------------------------------------

_reader = None  # Singleton, wird beim ersten Aufruf initialisiert


def ocr_text_aus_bild(bild_pfad: str) -> str:
    """
    Liest Text aus einem Bild per EasyOCR.
    Gibt den erkannten Rohtext zurück.
    """
    global _reader
    try:
        import easyocr
    except ImportError:
        return ""

    if _reader is None:
        _reader = easyocr.Reader(["de", "en"], gpu=False, verbose=False)

    bild_pfad_bearbeitet = vorverarbeite_bild(bild_pfad)

    ergebnisse = _reader.readtext(bild_pfad_bearbeitet, detail=0, paragraph=True)
    return "\n".join(ergebnisse)


# ---------------------------------------------------------------------------
# Nährwert-Parser (Regex-basiert)
# ---------------------------------------------------------------------------

# Mapping von Schlüsselwörtern → interne Feldnamen
FELD_MAPPING = {
    # Energie
    r"energie|energy|me\s*pfd|mj\s*me|umsetzbar": "energie_mj_me",

    # Protein
    r"rohprotein|crude\s*protein|xp\b": "rohprotein_pct",

    # Fett
    r"rohfett|crude\s*fat|xl\b|fett\b": "rohfett_pct",

    # Fasern
    r"rohfaser|crude\s*fibre|crude\s*fiber|xf\b": "rohfaser_pct",

    # Stärke
    r"st.rke|starch": "staerke_pct",

    # Zucker
    r"zucker|sugar": "zucker_pct",

    # Mineralstoffe
    r"calcium|ca\b": "calcium_g",
    r"phosphor|phosphorus|p\b": "phosphor_g",
    r"magnesium|mg\b": "magnesium_g",
    r"natrium|sodium|na\b": "natrium_g",
    r"kalium|potassium|k\b": "kalium_g",

    # Spurenelemente
    r"eisen|iron|fe\b": "eisen_mg",
    r"kupfer|copper|cu\b": "kupfer_mg",
    r"zink|zinc|zn\b": "zink_mg",
    r"mangan|manganese|mn\b": "mangan_mg",
    r"selen|selenium|se\b": "selen_mg",
    r"jod|iodine|iod": "jod_mg",

    # Vitamine
    r"vitamin\s*a|vit\.?\s*a": "vit_a_ie",
    r"vitamin\s*d|vit\.?\s*d": "vit_d_ie",
    r"vitamin\s*e|vit\.?\s*e": "vit_e_mg",
    r"vitamin\s*b1|thiamin": "vit_b1_mg",
    r"biotin": "biotin_mcg",

    # Lysin
    r"lysin": "lysin_g",
    r"methionin": "methionin_g",
}

# Einheitenumrechnung → Zieleinheit pro kg TS
# g → g (gleich), mg → mg (gleich), % bleibt %
# IE und IU bleiben als absolute Werte stehen
EINHEIT_NORMALISIERUNG = {
    # (quell_einheit, ziel_einheit): faktor
    ("g/kg", "g"):     1.0,
    ("mg/kg", "mg"):   1.0,
    ("ie/kg", "ie"):   1.0,
    ("iu/kg", "ie"):   1.0,
    ("%", "%"):        1.0,
    ("g/100g", "%"):   1.0,
    ("mg/100g", "%"):  0.1,
}


def extrahiere_naehrwerte(text: str) -> dict:
    """
    Analysiert OCR-Text und extrahiert Nährwerte.
    Gibt ein Dict mit Feldnamen → Wert zurück.
    """
    ergebnis = {}
    zeilen = text.split("\n")

    for zeile in zeilen:
        zeile_lower = zeile.lower().strip()
        if not zeile_lower:
            continue

        # Welches Nährwert-Feld?
        feld = None
        for muster, feldname in FELD_MAPPING.items():
            if re.search(muster, zeile_lower):
                feld = feldname
                break

        if feld is None:
            continue

        # Zahlenwert aus Zeile extrahieren
        # Sucht Muster wie: 12.5, 12,5, 1.500, 1500
        zahlen = re.findall(r"(\d+[.,]\d+|\d+)\s*(g/kg|mg/kg|%|ie/kg|iu/kg|g/100g|mg/100g|mj|ie)?",
                            zeile_lower)

        for zahl_str, einheit in zahlen:
            try:
                wert = float(zahl_str.replace(",", "."))

                # Einheit normalisieren
                einheit = einheit.strip() if einheit else ""

                # Energie: erwarte MJ/kg
                if feld == "energie_mj_me":
                    if wert > 100:  # vermutlich kcal
                        wert = wert / 239  # kcal → MJ (1 MJ ≈ 239 kcal)
                    ergebnis[feld] = round(wert, 2)

                # Prozentangaben bei Hauptnährstoffen
                elif feld in ("rohprotein_pct", "rohfett_pct", "rohfaser_pct",
                              "staerke_pct", "zucker_pct"):
                    if einheit == "g/kg":
                        wert = wert / 10  # g/kg → %
                    elif einheit == "g/100g":
                        pass  # bereits %
                    if 0 < wert <= 100:
                        ergebnis[feld] = round(wert, 2)

                # Mineralstoffe in g/kg TS
                elif feld in ("calcium_g", "phosphor_g", "magnesium_g",
                              "natrium_g", "kalium_g", "lysin_g", "methionin_g"):
                    if einheit == "%":
                        wert = wert * 10  # % → g/kg
                    elif einheit == "mg/kg":
                        wert = wert / 1000
                    if 0 < wert < 500:
                        ergebnis[feld] = round(wert, 3)

                # Spurenelemente in mg/kg TS
                elif feld in ("eisen_mg", "kupfer_mg", "zink_mg", "mangan_mg",
                              "selen_mg", "jod_mg"):
                    if einheit == "g/kg":
                        wert = wert * 1000
                    if 0 < wert < 10000:
                        ergebnis[feld] = round(wert, 2)

                break  # erste plausible Zahl je Zeile nehmen

            except ValueError:
                continue

    return ergebnis


# ---------------------------------------------------------------------------
# Vollständiger Import-Workflow
# ---------------------------------------------------------------------------

def importiere_etikett(bild_pfad: str) -> dict:
    """
    Kompletter Workflow: Bild → OCR → Nährwerte.
    Gibt dict mit erkannten Nährwerten + 'ocr_rohtext' zurück.
    """
    rohtext = ocr_text_aus_bild(bild_pfad)
    naehrwerte = extrahiere_naehrwerte(rohtext)
    naehrwerte["ocr_rohtext"] = rohtext
    return naehrwerte
