"""
Optimierungsassistent – Vorschlagslogik für Defizitausgleich und Variantenvergleich.

Architektur:
  - generiere_vorschlaege(): analysiert IST vs BEDARF und erzeugt Vorschläge
  - supplement_als_position(): wandelt ein Supplement + Tagesdosis in RationsPosition um
  - berechne_variante_ergebnis(): berechnet eine Variante aus DB-Daten
"""

from dataclasses import dataclass, field
from typing import List, Optional
import database
from rationsrechner import (
    RationsPosition, RationsErgebnis, berechne_ration,
    heu_als_position, position_aus_db_row,
)
from bedarfsberechnung import Bedarfswerte


# ---------------------------------------------------------------------------
# Nährstoff-Konfiguration (Feldname IST → Bedarf, Anzeigename, Einheit,
#                           Schwelle für Defizit-Anzeige in %)
# ---------------------------------------------------------------------------

NAEHRSTOFFE = [
    # (ist_feld,       bedarf_feld,    anzeige,          einheit, defizit_ab_pct, max_ueberschuss_pct)
    ("energie_mj",    "energie_mj",   "Energie",         "MJ",     5,  30),
    ("rohprotein_g",  "rp_g",         "Rohprotein",      "g",      5,  50),
    ("lysin_g",       "lysin_g",      "Lysin",           "g",      5,  80),
    ("methionin_g",   "methionin_g",  "Methionin",       "g",      5,  80),
    ("calcium_g",     "calcium_g",    "Calcium",         "g",      5,  80),
    ("phosphor_g",    "phosphor_g",   "Phosphor",        "g",      5,  80),
    ("magnesium_g",   "magnesium_g",  "Magnesium",       "g",      5,  80),
    ("natrium_g",     "natrium_g",    "Natrium",         "g",      5, 100),
    ("eisen_mg",      "eisen_mg",     "Eisen",           "mg",    10, 400),  # Überschuss fast immer vorhanden (Heu)
    ("kupfer_mg",     "kupfer_mg",    "Kupfer",          "mg",     5,  80),
    ("zink_mg",       "zink_mg",      "Zink",            "mg",     5,  80),
    ("mangan_mg",     "mangan_mg",    "Mangan",          "mg",     5,  80),
    ("selen_mg",      "selen_mg",     "Selen",           "mg",     5,  80),
    ("jod_mg",        "jod_mg",       "Jod",             "mg",     5, 100),
    ("vit_a_ie",      "vit_a_ie",     "Vitamin A",       "IE",     5,  80),
    ("vit_d_ie",      "vit_d_ie",     "Vitamin D",       "IE",     5,  80),
    ("vit_e_mg",      "vit_e_mg",     "Vitamin E",       "mg",     5,  80),
    ("vit_b1_mg",     "vit_b1_mg",    "Vitamin B1",      "mg",     5, 100),
    ("biotin_mcg",    "biotin_mcg",   "Biotin",          "µg",     5, 100),
]

# Nährstoffe, die per Supplementierung korrigiert werden können
SUPPLEMENTIERBARE_FELDER = {
    "selen_mg", "kupfer_mg", "zink_mg", "mangan_mg", "jod_mg",
    "vit_a_ie", "vit_d_ie", "vit_e_mg", "vit_b1_mg", "biotin_mcg",
    "lysin_g", "methionin_g", "threonin_g",
    "calcium_g", "phosphor_g", "magnesium_g", "natrium_g",
}


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class Vorschlag:
    """Korrekturvorschlag für einen einzelnen Nährstoff."""
    naehr_feld: str           # z.B. 'selen_mg'
    anzeige_name: str         # z.B. 'Selen'
    einheit: str              # z.B. 'mg'
    bedarf: float             # Tagesbedarf (in Einheit)
    ist: float                # aktuelle Aufnahme
    differenz: float          # bedarf - ist  (positiv = Defizit)
    differenz_pct: float      # Defizit in % (positiv = Unterversorgung)

    # Vorgeschlagene Supplemente (Liste, damit mehrere Optionen angeboten werden)
    supplemente: List[dict] = field(default_factory=list)   # supplement_katalog-Einträge
    empfohlene_dosis_g: float = 0.0   # Supplement-Dosis in g/Tag für 1. Option

    typ: str = "Defizit"    # "Defizit" | "Überversorgung" | "OK"
    hinweis: str = ""


@dataclass
class FutteranpassungVorschlag:
    """Vorschlag zur Mengenänderung bei Heu oder Kraftfutter."""
    typ: str           # "HeuReduzieren" | "HeuErhoehen" | "KraftfutterReduzieren"
    naehr_anzeige: str # z.B. "Energie"
    aktuell_kg: float
    vorgeschlagen_kg: float
    aenderung_kg: float   # positiv = mehr, negativ = weniger
    begruendung: str


# ---------------------------------------------------------------------------
# Hauptfunktionen
# ---------------------------------------------------------------------------

def generiere_vorschlaege(
    ist: RationsErgebnis,
    bedarf: Bedarfswerte,
    heu_menge_kg: float = 0.0,
) -> tuple[List[Vorschlag], List[FutteranpassungVorschlag]]:
    """
    Analysiert IST vs BEDARF und gibt zwei Listen zurück:
      1. Vorschlag-Liste (Defizite + Überschüsse mit Supplement-Optionen)
      2. FutteranpassungVorschlag-Liste (Heu/Kraftfutter-Mengenänderungen)
    """
    # Supplement-Katalog: Feld → Liste verfügbarer Supplemente
    alle_supps = database.alle_supplemente()
    supps_pro_feld: dict[str, list] = {}
    for s in alle_supps:
        supps_pro_feld.setdefault(s["naehr_feld"], []).append(s)

    vorschlaege: List[Vorschlag] = []
    anpassungen: List[FutteranpassungVorschlag] = []

    for (ist_feld, bed_feld, anzeige, einheit, def_ab, max_ue) in NAEHRSTOFFE:
        ist_val: float = getattr(ist, ist_feld, 0.0) or 0.0
        bed_val: float = getattr(bedarf, bed_feld, 0.0) or 0.0

        if bed_val <= 0:
            continue

        diff = bed_val - ist_val          # positiv = Defizit
        diff_pct = diff / bed_val * 100   # positiv = Defizit in %

        # Schwelle nicht erreicht → überspringen
        if abs(diff_pct) < def_ab:
            continue

        typ = "Defizit" if diff_pct > 0 else "Überversorgung"

        supps = supps_pro_feld.get(ist_feld, [])

        # Empfohlene Dosis zum ersten Supplement berechnen
        dosis_g = 0.0
        if typ == "Defizit" and supps:
            primary = supps[0]
            konzentration = primary.get("konzentration_je_kg") or 1.0
            # diff ist in Einheit (mg/g/IE/mcg), konzentration_je_kg ist pro kg Supplement
            # → dosis_kg = diff / konzentration_je_kg → dosis_g = dosis_kg × 1000
            if konzentration > 0:
                dosis_g = (diff / konzentration) * 1000  # in g/Tag

            # Auf Maximum begrenzen (wenn vorhanden)
            max_d = primary.get("max_tagesdosis_einheit")
            if max_d and dosis_g * konzentration / 1000 > max_d:
                dosis_g = max_d / konzentration * 1000

        hinweis = _generiere_hinweis(ist_feld, diff_pct, ist_val, bed_val, einheit)

        v = Vorschlag(
            naehr_feld=ist_feld,
            anzeige_name=anzeige,
            einheit=einheit,
            bedarf=bed_val,
            ist=ist_val,
            differenz=diff,
            differenz_pct=diff_pct,
            supplemente=supps,
            empfohlene_dosis_g=max(0.0, dosis_g),
            typ=typ,
            hinweis=hinweis,
        )
        vorschlaege.append(v)

    # Energie-Anpassung über Heu vorschlagen
    energie_ist  = getattr(ist, "energie_mj", 0.0) or 0.0
    energie_bed  = getattr(bedarf, "energie_mj", 0.0) or 0.0
    if energie_bed > 0:
        e_diff_pct = (energie_ist - energie_bed) / energie_bed * 100
        if e_diff_pct > 20 and heu_menge_kg > 0:
            # Überversorgung Energie → Heu reduzieren
            # grobe Schätzung: Energie pro kg Heu (~7–9 MJ/kg FM × 0,88 TS)
            energie_pro_kg_heu = energie_ist / heu_menge_kg if heu_menge_kg else 7.0
            ziel_heu = energie_bed * 0.85 / energie_pro_kg_heu  # Energie-Ziel 85% (Rest Kraftfutter)
            delta = ziel_heu - heu_menge_kg
            if delta < -0.3:  # mind. 300g Reduktion
                anpassungen.append(FutteranpassungVorschlag(
                    typ="HeuReduzieren",
                    naehr_anzeige="Energie",
                    aktuell_kg=heu_menge_kg,
                    vorgeschlagen_kg=max(2.0, ziel_heu),
                    aenderung_kg=delta,
                    begruendung=f"Energie-Überversorgung {e_diff_pct:+.0f}%. "
                                f"Heu auf ca. {max(2.0, ziel_heu):.1f} kg/Tag reduzieren.",
                ))
        elif e_diff_pct < -15:
            # Defizit Energie → Heu erhöhen (moderat)
            ziel_heu = heu_menge_kg * 1.2
            anpassungen.append(FutteranpassungVorschlag(
                typ="HeuErhoehen",
                naehr_anzeige="Energie",
                aktuell_kg=heu_menge_kg,
                vorgeschlagen_kg=ziel_heu,
                aenderung_kg=ziel_heu - heu_menge_kg,
                begruendung=f"Energie-Defizit {e_diff_pct:.0f}%. "
                            f"Heu auf ca. {ziel_heu:.1f} kg/Tag erhöhen oder Kraftfutter ergänzen.",
            ))

    # Rohprotein-Überversorgung
    rp_ist = getattr(ist, "rohprotein_g", 0.0) or 0.0
    rp_bed = getattr(bedarf, "rp_g", 0.0) or 0.0
    if rp_bed > 0:
        rp_pct = (rp_ist - rp_bed) / rp_bed * 100
        if rp_pct > 50:
            anpassungen.append(FutteranpassungVorschlag(
                typ="KraftfutterReduzieren",
                naehr_anzeige="Rohprotein",
                aktuell_kg=0.0,
                vorgeschlagen_kg=0.0,
                aenderung_kg=0.0,
                begruendung=f"Rohprotein-Überversorgung {rp_pct:+.0f}%. "
                            f"Auf proteinärmere Kraftfuttermittel oder geringere Mengen wechseln.",
            ))

    return vorschlaege, anpassungen


def supplement_als_position(supplement: dict, dosis_g_per_day: float) -> RationsPosition:
    """
    Wandelt ein Supplement und eine Tagesdosis (in g) in eine RationsPosition um,
    damit es direkt mit berechne_ration() verwendet werden kann.

    Das Supplement hat 0% Wassergehalt; menge_kg = dosis_g / 1000.
    """
    dosis_kg = dosis_g_per_day / 1000.0
    konzentration = supplement.get("konzentration_je_kg", 0.0)
    naehr_feld     = supplement.get("naehr_feld", "")
    einheit        = supplement.get("einheit", "mg")

    # Wirkstoffmenge pro kg Supplement (in der jeweiligen Einheit)
    # Im RationsPosition-Feld muss der Wert pro kg TS (= kg Supplement) stehen.
    feld_mapping = {
        "selen_mg":    "selen_mg",
        "kupfer_mg":   "kupfer_mg",
        "zink_mg":     "zink_mg",
        "mangan_mg":   "mangan_mg",
        "jod_mg":      "jod_mg",
        "kobalt_mg":   "kobalt_mg",
        "vit_a_ie":    "vit_a_ie",
        "vit_d_ie":    "vit_d_ie",
        "vit_e_mg":    "vit_e_mg",
        "vit_b1_mg":   "vit_b1_mg",
        "biotin_mcg":  "biotin_mcg",
        "lysin_g":     "lysin_g",
        "methionin_g": "methionin_g",
        "threonin_g":  None,   # kein direktes Feld in RationsPosition – wird ignoriert
        "calcium_g":   "calcium_g",
        "phosphor_g":  "phosphor_g",
        "magnesium_g": "magnesium_g",
        "natrium_g":   "natrium_g",
    }

    kwargs = {
        "futtermittel_id":  -(supplement.get("id", 0) + 10000),
        "name":             supplement.get("name", "Supplement"),
        "menge_kg":         dosis_kg,
        "wassergehalt_pct": 0.0,   # Pulver / Reinsubstanz
    }

    pos_feld = feld_mapping.get(naehr_feld)
    if pos_feld:
        kwargs[pos_feld] = konzentration  # Wirkstoff/kg Supplement = Wirkstoff/kg TS (da 0% Wasser)

    return RationsPosition(**kwargs)


def berechne_variante_ergebnis(
    positionen_daten: list,   # list of dicts aus variante_position Tabelle
    futtermittel_lookup: dict,   # {fm_id: fm_dict}
    supplement_lookup: dict,     # {supp_id: supp_dict}
    heu_lookup: dict,            # {heu_id: heu_dict}
) -> RationsErgebnis:
    """
    Berechnet das Rations-Ergebnis einer Variante.
    positionen_daten: Zeilen aus variante_position (quell_typ, *_id, menge_kg).
    """
    rations_positionen: List[RationsPosition] = []

    for pos in positionen_daten:
        typ   = pos.get("quell_typ")
        menge = pos.get("menge_kg", 0.0) or 0.0

        if typ == "futtermittel":
            fm_id = pos.get("futtermittel_id")
            fm = futtermittel_lookup.get(fm_id)
            if fm and menge > 0:
                rations_positionen.append(position_aus_db_row(fm, menge))

        elif typ == "heu":
            heu_id = pos.get("heu_qualitaet_id")
            heu = heu_lookup.get(heu_id)
            if heu and menge > 0:
                rations_positionen.append(heu_als_position(heu, menge))

        elif typ == "supplement":
            supp_id = pos.get("supplement_id")
            supp = supplement_lookup.get(supp_id)
            if supp and menge > 0:
                # menge in kg (also g/1000 × 1000 g/kg = g pro Tag)
                dosis_g = menge * 1000.0
                rations_positionen.append(supplement_als_position(supp, dosis_g))

    return berechne_ration(rations_positionen)


def _generiere_hinweis(feld: str, diff_pct: float,
                       ist: float, bedarf: float, einheit: str) -> str:
    """Gibt einen praxisnahen Hinweis für einen Nährstoff zurück."""
    hinweise = {
        "selen_mg": (
            "Selen ist essentiell für Muskel- und Immunfunktion. "
            "Überdosierung vermeiden (tox. Obergrenze ca. 0,5 mg/kg KGW/Tag bei Pferden). "
            "Selengehalt im Boden Mitteleuropas oft niedrig."
        ),
        "kupfer_mg": (
            "Kupfer wichtig für Huf- und Fellpigmentierung, Knochen, Enzymfunktionen. "
            "Zink und Eisen hemmen die Cu-Resorption (antagonistisches Verhältnis beachten)."
        ),
        "zink_mg": (
            "Zink essenziell für Wundheilung, Immunsystem, Huf und Fell. "
            "Mn:Zn-Ratio sollte ~3:1 bis 4:1 betragen."
        ),
        "mangan_mg": (
            "Mangan wichtig für Knorpelbildung und Reproduktion. "
            "Überschuss relativ gut toleriert, trotzdem Grenzen beachten."
        ),
        "vit_e_mg": (
            "Vitamin E als Antioxidans schützt Muskeln (EMND, EDM). "
            "Bei Muskelerkrankungen (PSSM, MIM) oft höhere Dosen empfohlen."
        ),
        "lysin_g": (
            "Lysin ist die erstlimitierende Aminosäure beim Pferd. "
            "Defizite beeinflussen Muskel- und Immunaufbau."
        ),
        "methionin_g": (
            "Methionin ist schwefelhaltige Aminosäure, wichtig für Huf, Fell und Leber."
        ),
        "calcium_g": (
            "Ca:P-Verhältnis sollte 1,5:1 bis 2:1 nicht unterschreiten (P > Ca vermeiden)."
        ),
        "phosphor_g": (
            "Überschuss an Phosphor hemmt Calciumresorption. Ca:P-Ratio prüfen."
        ),
        "magnesium_g": (
            "Mg-Mangel äussert sich oft in Nervosität, Muskelzittern. "
            "Weide-Tetanie-Risiko bei hohem K/Mg-Verhältnis im Gras."
        ),
        "jod_mg": (
            "Sowohl Unter- als auch Überversorgung mit Jod kann Schilddrüse schädigen."
        ),
        "biotin_mcg": (
            "Biotin verbessert Hufhornqualität. Effekte erst nach 6–12 Monaten sichtbar."
        ),
    }
    basis = hinweise.get(feld, "")

    if diff_pct > 0:
        status = f"Defizit: {abs(diff_pct):.0f}% unter Bedarf ({ist:.2g} von {bedarf:.2g} {einheit}/Tag)"
    else:
        status = f"Überschuss: {abs(diff_pct):.0f}% über Bedarf ({ist:.2g} vs {bedarf:.2g} {einheit}/Tag)"

    return f"{status}\n{basis}".strip()
