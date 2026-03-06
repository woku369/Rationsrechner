"""
Rationsberechnung - berechnet Nährstoffgehalt einer Futterration
und zeigt die Differenz zum Bedarf an.
"""

from dataclasses import dataclass, field
from typing import Optional
from bedarfsberechnung import Bedarfswerte


@dataclass
class RationsPosition:
    """Eine Komponente in der Ration."""
    futtermittel_id: int
    name: str
    menge_kg: float          # Frischmasse in kg
    wassergehalt_pct: float  # Wassergehalt in %

    # Nährwerte pro kg TS (aus Datenbank)
    energie_mj_me: float = 0.0
    rohprotein_pct: float = 0.0
    lysin_g: float = 0.0
    methionin_g: float = 0.0
    rohfett_pct: float = 0.0
    rohfaser_pct: float = 0.0
    staerke_pct: float = 0.0
    zucker_pct: float = 0.0
    nsc_pct: float = 0.0
    calcium_g: float = 0.0
    phosphor_g: float = 0.0
    magnesium_g: float = 0.0
    natrium_g: float = 0.0
    kalium_g: float = 0.0
    eisen_mg: float = 0.0
    kupfer_mg: float = 0.0
    zink_mg: float = 0.0
    mangan_mg: float = 0.0
    selen_mg: float = 0.0
    jod_mg: float = 0.0
    vit_a_ie: float = 0.0
    vit_d_ie: float = 0.0
    vit_e_mg: float = 0.0
    vit_b1_mg: float = 0.0
    biotin_mcg: float = 0.0


@dataclass
class RationsErgebnis:
    """Ergebnis der Rationsberechnung (Istwerte)."""
    trockenmasse_kg: float = 0.0
    energie_mj: float = 0.0
    rohprotein_g: float = 0.0
    lysin_g: float = 0.0
    methionin_g: float = 0.0
    rohfett_g: float = 0.0
    rohfaser_g: float = 0.0
    staerke_g: float = 0.0
    zucker_g: float = 0.0
    nsc_g: float = 0.0
    calcium_g: float = 0.0
    phosphor_g: float = 0.0
    magnesium_g: float = 0.0
    natrium_g: float = 0.0
    kalium_g: float = 0.0
    eisen_mg: float = 0.0
    kupfer_mg: float = 0.0
    zink_mg: float = 0.0
    mangan_mg: float = 0.0
    selen_mg: float = 0.0
    jod_mg: float = 0.0
    vit_a_ie: float = 0.0
    vit_d_ie: float = 0.0
    vit_e_mg: float = 0.0
    vit_b1_mg: float = 0.0
    biotin_mcg: float = 0.0

    # Prozentwerte bezogen auf TS
    nsc_pct_von_ts: float = 0.0
    staerke_pct_von_ts: float = 0.0


@dataclass
class DifferenzWerte:
    """Differenz Ist - Bedarf. Negativ = Unterversorgung."""
    energie_mj: float = 0.0
    rohprotein_g: float = 0.0
    lysin_g: float = 0.0
    calcium_g: float = 0.0
    phosphor_g: float = 0.0
    magnesium_g: float = 0.0
    natrium_g: float = 0.0
    kupfer_mg: float = 0.0
    zink_mg: float = 0.0
    mangan_mg: float = 0.0
    selen_mg: float = 0.0
    vit_e_mg: float = 0.0
    # Status
    nsc_uebersteigt_limit: bool = False
    staerke_uebersteigt_limit: bool = False
    # TS-Aufnahme in % des Bedarfs (>120% = Warnschwelle, >150% = kritisch)
    ts_ueberschreitung_pct: float = 0.0


# ---------------------------------------------------------------------------

def berechne_ration(positionen: list[RationsPosition]) -> RationsErgebnis:
    """
    Berechnet den Gesamt-Nährstoffgehalt einer Futterration.
    Alle Mengen in Frischmasse, alle Nährwerte pro kg TS.
    Gibt absolute Mengen pro Tag zurück.
    """
    erg = RationsErgebnis()

    for pos in positionen:
        # Trockenmasse dieser Position
        ts_faktor = 1.0 - pos.wassergehalt_pct / 100.0
        tm_kg = pos.menge_kg * ts_faktor

        erg.trockenmasse_kg += tm_kg
        erg.energie_mj      += tm_kg * pos.energie_mj_me
        erg.rohprotein_g    += tm_kg * pos.rohprotein_pct * 10      # % → g/kg → g
        erg.lysin_g         += tm_kg * pos.lysin_g
        erg.methionin_g     += tm_kg * pos.methionin_g
        erg.rohfett_g       += tm_kg * pos.rohfett_pct * 10
        erg.rohfaser_g      += tm_kg * pos.rohfaser_pct * 10
        erg.staerke_g       += tm_kg * pos.staerke_pct * 10
        erg.zucker_g        += tm_kg * pos.zucker_pct * 10
        erg.nsc_g           += tm_kg * pos.nsc_pct * 10
        erg.calcium_g       += tm_kg * pos.calcium_g
        erg.phosphor_g      += tm_kg * pos.phosphor_g
        erg.magnesium_g     += tm_kg * pos.magnesium_g
        erg.natrium_g       += tm_kg * pos.natrium_g
        erg.kalium_g        += tm_kg * pos.kalium_g
        erg.eisen_mg        += tm_kg * pos.eisen_mg
        erg.kupfer_mg       += tm_kg * pos.kupfer_mg
        erg.zink_mg         += tm_kg * pos.zink_mg
        erg.mangan_mg       += tm_kg * pos.mangan_mg
        erg.selen_mg        += tm_kg * pos.selen_mg
        erg.jod_mg          += tm_kg * pos.jod_mg
        erg.vit_a_ie        += tm_kg * pos.vit_a_ie
        erg.vit_d_ie        += tm_kg * pos.vit_d_ie
        erg.vit_e_mg        += tm_kg * pos.vit_e_mg
        erg.vit_b1_mg       += tm_kg * pos.vit_b1_mg
        erg.biotin_mcg      += tm_kg * pos.biotin_mcg

    if erg.trockenmasse_kg > 0:
        erg.staerke_pct_von_ts = (erg.staerke_g / erg.trockenmasse_kg) / 10
        erg.nsc_pct_von_ts     = (erg.nsc_g     / erg.trockenmasse_kg) / 10

    return erg


def berechne_differenz(ist: RationsErgebnis, bedarf: Bedarfswerte,
                       diagnosen: list = None) -> DifferenzWerte:
    """
    Berechnet die Differenz Ist minus Bedarf.
    Negative Werte = Unterversorgung.
    """
    dif = DifferenzWerte()
    dif.energie_mj    = ist.energie_mj    - bedarf.energie_mj
    dif.rohprotein_g  = ist.rohprotein_g  - bedarf.rp_g
    dif.lysin_g       = ist.lysin_g       - bedarf.lysin_g
    dif.calcium_g     = ist.calcium_g     - bedarf.calcium_g
    dif.phosphor_g    = ist.phosphor_g    - bedarf.phosphor_g
    dif.magnesium_g   = ist.magnesium_g   - bedarf.magnesium_g
    dif.natrium_g     = ist.natrium_g     - bedarf.natrium_g
    dif.kupfer_mg     = ist.kupfer_mg     - bedarf.kupfer_mg
    dif.zink_mg       = ist.zink_mg       - bedarf.zink_mg
    dif.mangan_mg     = ist.mangan_mg     - bedarf.mangan_mg
    dif.selen_mg      = ist.selen_mg      - bedarf.selen_mg
    dif.vit_e_mg      = ist.vit_e_mg      - bedarf.vit_e_mg

    if diagnosen is None:
        diagnosen = []

    # NSC-Limit-Prüfung
    if bedarf.nsc_max_pct and ist.nsc_pct_von_ts > bedarf.nsc_max_pct:
        dif.nsc_uebersteigt_limit = True
    if bedarf.stärke_max_pct and ist.staerke_pct_von_ts > bedarf.stärke_max_pct:
        dif.staerke_uebersteigt_limit = True

    # TS-Überschreitung berechnen (>120% = Hinweis, Mineralwerte werden dann
    # fälschlicherweise als überhöht ausgewiesen – eigentlich ein Mengenproblem)
    if bedarf.trockenmasse_kg > 0:
        dif.ts_ueberschreitung_pct = (
            ist.trockenmasse_kg / bedarf.trockenmasse_kg * 100
        )

    return dif


def position_aus_db_row(row: dict, menge_kg: float) -> RationsPosition:
    """Erstellt eine RationsPosition aus einem Datenbankdatensatz."""
    def s(key):
        return row.get(key) or 0.0

    nsc = s("nsc_pct") or (s("staerke_pct") + s("zucker_pct"))

    return RationsPosition(
        futtermittel_id = row["id"],
        name            = row["name"],
        menge_kg        = menge_kg,
        wassergehalt_pct= row.get("wassergehalt_pct") or 12.0,
        energie_mj_me   = s("energie_mj_me"),
        rohprotein_pct  = s("rohprotein_pct"),
        lysin_g         = s("lysin_g"),
        methionin_g     = s("methionin_g"),
        rohfett_pct     = s("rohfett_pct"),
        rohfaser_pct    = s("rohfaser_pct"),
        staerke_pct     = s("staerke_pct"),
        zucker_pct      = s("zucker_pct"),
        nsc_pct         = nsc,
        calcium_g       = s("calcium_g"),
        phosphor_g      = s("phosphor_g"),
        magnesium_g     = s("magnesium_g"),
        natrium_g       = s("natrium_g"),
        kalium_g        = s("kalium_g"),
        eisen_mg        = s("eisen_mg"),
        kupfer_mg       = s("kupfer_mg"),
        zink_mg         = s("zink_mg"),
        mangan_mg       = s("mangan_mg"),
        selen_mg        = s("selen_mg"),
        jod_mg          = s("jod_mg"),
        vit_a_ie        = s("vit_a_ie"),
        vit_d_ie        = s("vit_d_ie"),
        vit_e_mg        = s("vit_e_mg"),
        vit_b1_mg       = s("vit_b1_mg"),
        biotin_mcg      = s("biotin_mcg"),
    )


def heu_als_position(qualitaet: dict, menge_kg: float,
                     verlust_pct: float = 0.0) -> RationsPosition:
    """Erstellt eine RationsPosition für Heu aus einem Heu-Qualitätsdatensatz."""
    e_mitte = (qualitaet["energie_min"] + qualitaet["energie_max"]) / 2
    rp_mitte = (qualitaet["rp_min_pct"] + qualitaet["rp_max_pct"]) / 2
    zs_max = qualitaet.get("zucker_staerke_max_pct", 12.0)
    nsc_heu = zs_max * 0.8  # konservative Schätzung
    aufgenommen_kg = menge_kg * (1.0 - verlust_pct / 100.0)

    return RationsPosition(
        futtermittel_id      = -qualitaet["id"],
        name                 = f"Heu ({qualitaet['bezeichnung']})",
        menge_kg             = aufgenommen_kg,
        menge_verabreicht_kg = menge_kg,
        verlust_pct          = verlust_pct,
        wassergehalt_pct= 12.0,
        energie_mj_me   = e_mitte,
        rohprotein_pct  = rp_mitte,
        lysin_g         = rp_mitte * 0.038,    # Lysin ~3,8% vom RP bei Heu
        rohfaser_pct    = 30.0,
        zucker_pct      = zs_max * 0.6,
        staerke_pct     = zs_max * 0.2,
        nsc_pct         = nsc_heu,
        calcium_g       = 5.0,
        phosphor_g      = 2.0,
        magnesium_g     = 1.5,
        natrium_g       = 0.5,
        kalium_g        = 20.0,
        eisen_mg        = 200.0,
        kupfer_mg       = 6.0,
        zink_mg         = 25.0,
        mangan_mg       = 60.0,
        selen_mg        = 0.05,
        vit_e_mg        = 20.0,    # konservativ (gelagertes Heu), Frischheu bis 40 mg/kg TS
        vit_a_ie        = 1500.0,  # DLG-Mittelwert Wiesenheu 800–2500 IE/kg TS;
                                   # nach 6 Mon. Lagerung ggf. unter 1000 IE/kg TS
    )
