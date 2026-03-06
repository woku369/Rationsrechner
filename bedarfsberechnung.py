"""
Nährstoffbedarfsberechnung nach GfE (Gesellschaft für Ernährungsphysiologie)
Empfehlungen zur Energie- und Nährstoffversorgung der Pferde, 6. Auflage
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class PferdeParameter:
    """Eingabeparameter für ein Pferd."""
    gewicht_kg: float
    alter_jahre: float
    rasse_typ: str = "Warmblut (allgemein)"   # siehe RASSENFAKTOR_ENERGIE für vollständige Liste
    nutzung: str = "Freizeit"        # Freizeit | Leichte_Arbeit | Mittlere_Arbeit | Schwere_Arbeit
    geschlecht: str = "Stute"        # Stute | Hengst | Wallach
    traechtigkeit: int = 0           # 0 = nein, 1..11 = Trächtigkeitsmonat
    laktation: int = 0               # 0 = nein, 1..6 = Laktationsmonat
    diagnosen: list = field(default_factory=list)
        # mögliche Werte: EMS, Cushing, PSSM1, PSSM2, MIM, Hufrehe, COPD

    # Individuelle Overrides (None = GfE-Standard)
    override_energie_mj:  Optional[float] = None
    override_rp_g:        Optional[float] = None
    override_selen_mg:    Optional[float] = None
    override_nsc_max_pct: Optional[float] = None
    override_begruendung: Optional[str]   = None
    raufutter_min_kg:     Optional[float] = None   # Verhaltensminimum Raufutter


@dataclass
class Bedarfswerte:
    """Täglicher Nährstoffbedarf."""
    # Energie
    energie_mj: float = 0.0         # MJ ME/Tag

    # Protein
    rp_g: float = 0.0               # Rohprotein g/Tag
    lysin_g: float = 0.0            # g/Tag
    methionin_g: float = 0.0        # g/Tag

    # Makromineralien (g/Tag)
    calcium_g: float = 0.0
    phosphor_g: float = 0.0
    magnesium_g: float = 0.0
    natrium_g: float = 0.0
    kalium_g: float = 0.0

    # Spurenelemente (mg/Tag)
    eisen_mg: float = 0.0
    kupfer_mg: float = 0.0
    zink_mg: float = 0.0
    mangan_mg: float = 0.0
    selen_mg: float = 0.0
    jod_mg: float = 0.0
    kobalt_mg: float = 0.0

    # Vitamine
    vit_a_ie: float = 0.0           # IE/Tag
    vit_d_ie: float = 0.0           # IE/Tag
    vit_e_mg: float = 0.0           # mg/Tag
    vit_b1_mg: float = 0.0          # mg/Tag
    biotin_mcg: float = 0.0         # µg/Tag

    # Sondergrenzen (bei Erkrankungen)
    nsc_max_pct: Optional[float] = None   # max. NSC (Stärke+Zucker) in % der TS
    stärke_max_pct: Optional[float] = None
    trockenmasse_kg: float = 0.0         # empfohlene TS-Aufnahme/Tag
    trockenmasse_quelle: str = "GfE Nährstoffbedarf"  # oder "Verhaltensminimum"


# ---------------------------------------------------------------------------
# Faktoren
# ---------------------------------------------------------------------------

# Nutzungs-Energiefaktoren (Multiplikator auf Erhaltungsbedarf)
# Quelle: GfE 2014 – Erhaltung = 1.0, Freizeit/Weidegang = 1.10
NUTZUNGSFAKTOR_ENERGIE = {
    "Freizeit":        1.10,   # GfE: Erhaltung=1.0, Freizeit/Weidegang max. 1.10
    "Leichte_Arbeit":  1.25,   # angepasst nach unten wegen verschobener Skala
    "Mittlere_Arbeit": 1.50,
    "Schwere_Arbeit":  1.85,
}

# Nutzungs-Proteinfaktoren
NUTZUNGSFAKTOR_PROTEIN = {
    "Freizeit":        1.10,
    "Leichte_Arbeit":  1.15,
    "Mittlere_Arbeit": 1.35,   # K3: GfE-Soll 900-1100g/500kg → 945g ✅
    "Schwere_Arbeit":  1.60,   # K3: GfE-Soll 1200-1500g/600kg → 1344g ✅
}

# Rasse-/Typ-Korrekturfaktor auf Erhaltungsenergie
# Grundlage: GfE 2014, angepasst nach Literatur zu rassetypischen Erhaltungsbedarfen.
# Faktor wird auf den Basiserhaltungsbedarf (MJ ME/Tag) multipliziert.
RASSENFAKTOR_ENERGIE = {
    # ── Warmblut (Sportpferde, europäische Reitpferde) ─────────────
    "Warmblut (allgemein)": 1.00,
    "Hannoveraner":         1.00,
    "Holsteiner":           1.00,
    "Westfale":             1.00,
    "Oldenburger":          1.00,
    "Trakehner":            1.00,
    "KWPN":                 1.00,
    "Bayerisches Warmblut": 1.00,
    "Schwedisches Warmblut":1.00,
    "Selle Français":       1.00,
    "Österreichisches Warmblut": 1.00,
    "Andalusier / PRE":     1.00,
    "Lusitano":             1.00,
    "Appaloosa":            0.97,   # leichter Futtertyp
    "Quarter Horse":        0.95,   # leichter Futtertyp (American stock horse)
    "Paint Horse":          0.95,
    "Morgan":               0.95,
    # ── Vollblut / orientalische Rassen ────────────────────────────
    "Vollblut (Thoroughbred)": 1.10,  # höherer Grundumsatz
    "Araber / Vollblutaraber": 1.05,
    "Anglo-Araber":         1.05,
    "Shagya-Araber":        1.03,
    # ── Friesen / Halbblut ─────────────────────────────────────────
    "Friese":               0.93,   # schwerer Körperbau, leichter Futtertyp
    "Freiberger":           0.93,
    "Rocky Mountain Horse": 0.95,
    # ── Haflinger & Cobs (leichte Futtertypen) ─────────────────────
    "Haflinger":            0.88,   # bekannter leichter Futtertyp
    "Tinker / Irish Cob":   0.87,   # sehr leichter Futtertyp
    "Gypsy Cob":            0.87,
    "Shire":                0.90,
    "Clydesdale":           0.90,
    "Percheron":            0.90,
    # ── Kaltblut ───────────────────────────────────────────────────
    "Kaltblut (allgemein)": 0.90,
    "Noriker":              0.90,
    "Belgier":              0.88,
    "Schwarzwälder Fuchs":  0.90,
    "Süddeutsches Kaltblut":0.90,
    "Schleswig":            0.90,
    # ── Pony / Kleinpferd ──────────────────────────────────────────
    "Pony (allgemein)":     0.85,
    "Deutsches Reitpony":   0.85,
    "Connemara":            0.85,
    "New Forest Pony":      0.85,
    "Paso Fino":            0.85,
    "Lewitzer":             0.85,
    "Dülmener":             0.84,
    "Fjordpferd":           0.83,   # leichter Futtertyp
    "Welsh Pony":           0.83,
    "Exmoor Pony":          0.82,
    "Isländer":             0.80,   # extrem leichter Futtertyp
    "Shetland Pony":        0.78,   # sehr leichter Futtertyp
    # ── Rückwärtskompatibilität (alte DB-Einträge) ──────────────────
    "Warmblut":             1.00,
    "Vollblut":             1.10,
    "Pony":                 0.85,
    "Kaltblut":             0.90,
}


# ---------------------------------------------------------------------------
# Kernberechnung
# ---------------------------------------------------------------------------

def berechne_bedarf(p: PferdeParameter) -> Bedarfswerte:
    """
    Berechnet den täglichen Nährstoffbedarf nach GfE-Empfehlungen.
    Gibt ein Bedarfswerte-Objekt zurück.
    """
    b = Bedarfswerte()
    kgw = p.gewicht_kg
    rf = RASSENFAKTOR_ENERGIE.get(p.rasse_typ, 1.0)

    # ----------------------------------------------------------------
    # 1. TROCKENMASSE-Aufnahme (GfE: 1,5–2% des KGW/Tag als TS)
    # ----------------------------------------------------------------
    if p.nutzung in ("Mittlere_Arbeit", "Schwere_Arbeit"):
        tm_pct = 0.020
    else:
        tm_pct = 0.018

    # K6: Jungpferde haben höhere TS-Aufnahme als adulte Pferde (GfE: <2J 2.5-3.5%)
    if p.alter_jahre < 2:
        tm_pct = 0.030
    elif p.alter_jahre < 3:
        tm_pct = 0.025

    b.trockenmasse_kg = kgw * tm_pct

    # ----------------------------------------------------------------
    # 2. ENERGIE (MJ ME/Tag)
    # Erhaltungsbedarf: GfE 2014 (6. Aufl.) E_erh = 0.53 * KGW^0.75 * rf
    # ----------------------------------------------------------------
    e_erhalt = 0.53 * (kgw ** 0.75) * rf

    nf_e = NUTZUNGSFAKTOR_ENERGIE.get(p.nutzung, 1.2)
    b.energie_mj = e_erhalt * nf_e

    # Trächtigkeit: letztes Drittel (ab Monat 8) → +10–25%
    if p.traechtigkeit >= 9:
        b.energie_mj *= 1.25
    elif p.traechtigkeit >= 7:
        b.energie_mj *= 1.12

    # Laktation: frühe Laktation +50%, spätere +25%
    if p.laktation >= 1:
        if p.laktation <= 3:
            b.energie_mj *= 1.50
        else:
            b.energie_mj *= 1.25

    # Jungpferde < 3 Jahre: Wachstumszuschlag
    if p.alter_jahre < 1:
        b.energie_mj *= 1.70
    elif p.alter_jahre < 2:
        b.energie_mj *= 1.40
    elif p.alter_jahre < 3:
        b.energie_mj *= 1.20

    # Hengst: +10%
    if p.geschlecht == "Hengst" and p.nutzung != "Freizeit":
        b.energie_mj *= 1.10

    # ----------------------------------------------------------------
    # 3. ROHPROTEIN (g/Tag)
    # GfE 2014: Erhaltung ~1,26 g nXP/kg KGW → 1.4 g RP/kg KGW (RP-Bedarf
    # ist NICHT rassespezifisch – nur Energiebedarf wird mit rf skaliert)
    # ----------------------------------------------------------------
    nf_p = NUTZUNGSFAKTOR_PROTEIN.get(p.nutzung, 1.1)
    b.rp_g = 1.4 * kgw * nf_p

    if p.laktation >= 1:
        b.rp_g *= 1.40 if p.laktation <= 3 else 1.20
    if p.traechtigkeit >= 9:
        b.rp_g *= 1.20
    if p.alter_jahre < 2:
        b.rp_g *= 1.30
    elif p.alter_jahre < 3:   # K5: 2-3J noch aktiver Muskelaufbau
        b.rp_g *= 1.10

    # K4: Hengst – leicht erhöhter RP-Bedarf (Spermaproduktion + Muskelaufbau)
    if p.geschlecht == "Hengst":
        b.rp_g *= 1.05

    # Lysin: direkt über KGW (0.043 * RP-Brutto war ~2.5x zu hoch, da GfE-Faktor
    # sich auf verdauliches Protein nXP bezieht, nicht auf Brutto-RP)
    b.lysin_g = 0.030 * kgw * nf_p
    # Methionin analog: robuste KGW-basierte Formel
    b.methionin_g = 0.014 * kgw * nf_p

    # K4: Lysin/Methionin-Zuschlag Hengst (nach Basisberechnung anwenden)
    if p.geschlecht == "Hengst":
        b.lysin_g     *= 1.05
        b.methionin_g *= 1.05

    # ----------------------------------------------------------------
    # 4. MINERALSTOFFE
    # ----------------------------------------------------------------
    # Calcium (g/Tag): GfE Erhaltung 0.04 g/kg KGW
    b.calcium_g   = 0.040 * kgw
    b.phosphor_g  = 0.028 * kgw
    b.magnesium_g = 0.015 * kgw
    b.natrium_g   = 0.020 * kgw
    b.kalium_g    = 0.050 * kgw

    # Zuschläge Arbeit
    if p.nutzung == "Mittlere_Arbeit":
        b.calcium_g   *= 1.30
        b.phosphor_g  *= 1.25
        b.magnesium_g *= 1.30
        b.natrium_g   *= 2.00
    elif p.nutzung == "Schwere_Arbeit":
        b.calcium_g   *= 1.50
        b.phosphor_g  *= 1.40
        b.magnesium_g *= 1.50
        b.natrium_g   *= 3.00

    # Laktation
    if p.laktation >= 1:
        b.calcium_g   *= 1.80
        b.phosphor_g  *= 1.50
        b.magnesium_g *= 1.40

    # K1: Trächtigkeit – Ca/P-Zuschlag für Knochenaufbau des Fohlens (GfE 6. Aufl.)
    if p.traechtigkeit >= 9:
        b.calcium_g  *= 1.50   # GfE: letztes Drittel +50% Ca
        b.phosphor_g *= 1.40
    elif p.traechtigkeit >= 7:
        b.calcium_g  *= 1.25
        b.phosphor_g *= 1.20

    # ----------------------------------------------------------------
    # 5. SPURENELEMENTE (mg/Tag)
    # ----------------------------------------------------------------
    b.eisen_mg   = 0.045 * kgw * nf_e     # 40–60 mg/kg TS
    b.kupfer_mg  = max(100, 0.12 * kgw)
    b.zink_mg    = max(400, 0.40 * kgw)
    b.mangan_mg  = max(400, 0.40 * kgw)
    b.selen_mg   = max(0.5,  0.0015 * kgw)   # K2: Min 0.5 statt 1.0 – Toxgrenze Kleinpferde
    b.jod_mg     = max(3.5,  0.003 * kgw)
    b.kobalt_mg  = max(0.5,  0.0005 * kgw)

    if p.nutzung in ("Mittlere_Arbeit", "Schwere_Arbeit"):
        b.kupfer_mg  *= 1.25
        b.zink_mg    *= 1.30
        b.mangan_mg  *= 1.25

    # MIM: erhöhter Vit-E und Se-Bedarf
    if "MIM" in p.diagnosen or "PSSM2" in p.diagnosen:
        b.selen_mg   *= 1.50
        b.kupfer_mg  *= 1.20

    # ----------------------------------------------------------------
    # 6. VITAMINE
    # ----------------------------------------------------------------
    b.vit_a_ie   = 44 * kgw      # IE/Tag
    b.vit_d_ie   = 6.6 * kgw
    b.vit_e_mg   = 1.0 * kgw

    if p.nutzung in ("Mittlere_Arbeit", "Schwere_Arbeit"):
        b.vit_e_mg *= 2.0

    if "MIM" in p.diagnosen:
        b.vit_e_mg = max(b.vit_e_mg, 2000)  # min. 2000 mg/Tag bei MIM

    b.vit_b1_mg  = 0.030 * kgw
    b.biotin_mcg = 0.16 * kgw    # µg/Tag; bei Hufproblemen mind. 20.000 µg

    # ----------------------------------------------------------------
    # 7. SENIOREN-ANPASSUNG (> 20 Jahre)
    # Verdaulichkeit von RP und Phosphor sinkt; Vit-E-Bedarf steigt;
    # Trockenmasseaufnahme oft durch Zahnprobleme eingeschränkt.
    # ----------------------------------------------------------------
    if p.alter_jahre >= 20:
        b.rp_g        *= 1.15   # geringere RP-Verdaulichkeit ab 20 Jahren
        b.lysin_g     *= 1.15
        b.methionin_g *= 1.15
        b.phosphor_g  *= 1.10   # leicht reduzierte P-Verfügbarkeit
        b.vit_e_mg    *= 1.20   # erhöhter antioxidativer Bedarf
        b.trockenmasse_kg *= 0.95  # Zahnprobleme → geringere TS-Aufnahme

    # ----------------------------------------------------------------
    # 8. SONDERGRENZEN bei Erkrankungen
    # ----------------------------------------------------------------
    if any(d in p.diagnosen for d in ("EMS", "Cushing")):
        b.nsc_max_pct = 10.0    # max. 10% NSC der TS
        b.stärke_max_pct = 8.0

    if "PSSM1" in p.diagnosen:
        b.nsc_max_pct = 10.0
        b.stärke_max_pct = 5.0   # sehr strikt bei PSSM Typ 1

    if "PSSM2" in p.diagnosen or "MIM" in p.diagnosen:
        b.nsc_max_pct = 15.0
        b.stärke_max_pct = 10.0

    # Hufrehe: NSC-Limit identisch zu EMS (Hauptrisikofaktor: Zuckerzufuhr)
    if "Hufrehe" in p.diagnosen:
        b.nsc_max_pct = 10.0
        b.stärke_max_pct = 8.0
        b.biotin_mcg = max(b.biotin_mcg, 20000)  # Biotinbedarf bei Hufproblemen

    # ----------------------------------------------------------------
    # 9. INDIVIDUELLE OVERRIDES (überschreiben GfE-Berechnung)
    # ----------------------------------------------------------------
    if p.override_energie_mj is not None:
        b.energie_mj = p.override_energie_mj
    if p.override_rp_g is not None:
        b.rp_g = p.override_rp_g
    if p.override_selen_mg is not None:
        b.selen_mg = p.override_selen_mg
    if p.override_nsc_max_pct is not None:
        b.nsc_max_pct = p.override_nsc_max_pct

    # Verhaltensminimum Raufutter (schlägt GfE-TS wenn höher)
    if p.raufutter_min_kg is not None:
        raufutter_ts = p.raufutter_min_kg * 0.88   # Heu ~88% TS
        if raufutter_ts > b.trockenmasse_kg:
            b.trockenmasse_kg = raufutter_ts
            b.trockenmasse_quelle = "Verhaltensminimum"

    return b


# ---------------------------------------------------------------------------
# Übersichtstext
# ---------------------------------------------------------------------------

NUTZUNG_LABELS = {
    "Freizeit":        "Freizeit / Erhaltung",
    "Leichte_Arbeit":  "Leichte Arbeit (1–3 Std./Woche)",
    "Mittlere_Arbeit": "Mittlere Arbeit (3–5 Std./Woche)",
    "Schwere_Arbeit":  "Schwere Arbeit (>5 Std./Woche)",
}


def bedarf_als_text(p: PferdeParameter, b: Bedarfswerte) -> str:
    """Gibt eine formatierte Übersicht der Bedarfswerte zurück."""
    lines = [
        f"Bedarfsberechnung nach GfE",
        f"{'=' * 40}",
        f"Pferd:        {p.gewicht_kg:.0f} kg, {p.alter_jahre:.1f} Jahre, {p.rasse_typ}",
        f"Nutzung:      {NUTZUNG_LABELS.get(p.nutzung, p.nutzung)}",
    ]
    if p.diagnosen:
        lines.append(f"Diagnosen:    {', '.join(p.diagnosen)}")
    lines += [
        f"",
        f"Trockenmasse:     {b.trockenmasse_kg:.1f} kg/Tag",
        f"Energie:          {b.energie_mj:.1f} MJ ME/Tag",
        f"Rohprotein:       {b.rp_g:.0f} g/Tag",
        f"Lysin:            {b.lysin_g:.1f} g/Tag",
        f"",
        f"Calcium:          {b.calcium_g:.1f} g/Tag",
        f"Phosphor:         {b.phosphor_g:.1f} g/Tag",
        f"Magnesium:        {b.magnesium_g:.1f} g/Tag",
        f"Natrium:          {b.natrium_g:.1f} g/Tag",
        f"",
        f"Kupfer:           {b.kupfer_mg:.0f} mg/Tag",
        f"Zink:             {b.zink_mg:.0f} mg/Tag",
        f"Mangan:           {b.mangan_mg:.0f} mg/Tag",
        f"Selen:            {b.selen_mg:.2f} mg/Tag",
        f"",
        f"Vitamin A:        {b.vit_a_ie:.0f} IE/Tag",
        f"Vitamin E:        {b.vit_e_mg:.0f} mg/Tag",
    ]
    if b.nsc_max_pct:
        lines.append(f"NSC-Limit:        max. {b.nsc_max_pct:.0f}% der TS  ⚠")
    if b.stärke_max_pct:
        lines.append(f"Stärke-Limit:     max. {b.stärke_max_pct:.0f}% der TS  ⚠")
    if "Hufrehe" in p.diagnosen:
        lines += [
            "",
            "⚠  Hufrehe-Hinweise:",
            "   • NSC max. 10% der TS (Stärke + Zucker streng begrenzen)",
            "   • Weidegang nur frühmorgens nach Frost, max. 1–2 h",
            "   • Heu einweichen (30–60 min) um Zucker auszuspülen",
            "   • Kein frisches Grüngras, kein Obst, keine Stärketräger",
        ]
    if "COPD" in p.diagnosen:
        lines += [
            "",
            "⚠  COPD / Dämpfigkeit-Hinweise:",
            "   • Heu nur gut eingeweicht anbieten (30–60 min) oder als Heucobs",
            "   • Heulage / Silage ist Alternative zu trockenem Heu",
            "   • Keine staubigen Kraftfutter, keine trockenen Mischungen",
            "   • Stallhaltung während Pollenflug und hoher Feuchtigkeit reduzieren",
        ]
    if p.alter_jahre >= 20:
        lines += [
            "",
            f"i  Senior ({p.alter_jahre:.0f} Jahre): RP- und Vit-E-Bedarf erhöht,"
            " Trockenmasse-Aufnahme reduziert.",
        ]
    return "\n".join(lines)
