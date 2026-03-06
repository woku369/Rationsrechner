"""
Datenbankschicht - SQLite Schema und Datenzugriff
Pferde-Rationsrechner
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(os.path.abspath(__file__)).parent / "rationsrechner.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Erstellt alle Tabellen falls nicht vorhanden und befüllt Stammdaten."""
    with get_connection() as conn:
        _create_tables(conn)
        # Migration: Heu-Felder in rationen (falls Tabelle schon vor diesem Update existiert)
        for col, typ in [("heu_qualitaet_id", "INTEGER"), ("heu_menge_kg", "REAL DEFAULT 0")]:
            try:
                conn.execute(f"ALTER TABLE rationen ADD COLUMN {col} {typ}")
            except Exception:
                pass  # Spalte bereits vorhanden
        # Testdatensätze bereinigen
        conn.execute("DELETE FROM futtermittel WHERE name LIKE '__TEST%'")
        _seed_stammdaten(conn)
        _seed_markenfuttermittel(conn)
        conn.commit()


# ======================================================================
# MISCHFUTTERMITTEL
# ======================================================================

NAEHR_FELDER = [
    "energie_mj_me", "rohprotein_pct", "lysin_g", "methionin_g",
    "rohfett_pct", "rohfaser_pct", "staerke_pct", "zucker_pct",
    "calcium_g", "phosphor_g", "magnesium_g", "natrium_g", "kalium_g",
    "eisen_mg", "kupfer_mg", "zink_mg", "mangan_mg", "selen_mg",
    "jod_mg", "kobalt_mg", "vit_a_ie", "vit_d_ie", "vit_e_mg",
    "vit_b1_mg", "biotin_mcg",
]


def berechne_misch_naehrstoffe(komponenten: list) -> dict:
    """
    Berechnet gewichtete Nährwerte einer Eigenmischung.
    komponenten: list of (fm_dict, anteil_kg_frisch).
    Gibt dict der Nährwerte zurück (alles je kg TS der Mischung) +
    'wassergehalt_pct' der Gesamtmischung + 'anteil_gesamt_kg'.
    """
    if not komponenten:
        return {}

    # TS-kg pro Komponente
    dm_kg = []
    for fm, kg in komponenten:
        wasser = fm.get("wassergehalt_pct") or 12.0
        dm_kg.append(kg * (1.0 - wasser / 100.0))

    total_dm = sum(dm_kg)
    total_fm = sum(kg for _, kg in komponenten)
    if total_dm == 0:
        return {}

    result = {}
    for feld in NAEHR_FELDER:
        wert = sum(
            (fm.get(feld) or 0.0) * dm
            for (fm, _), dm in zip(komponenten, dm_kg)
        ) / total_dm
        result[feld] = wert  # 0.0 wenn keine der Komponenten den Wert hat

    # NSC = Stärke + Zucker
    result["nsc_pct"] = (result.get("staerke_pct") or 0) + (result.get("zucker_pct") or 0)

    # Wassergehalt der Gesamtmischung
    result["wassergehalt_pct"] = (1.0 - total_dm / total_fm) * 100.0 if total_fm > 0 else 12.0
    result["_anteil_gesamt_kg"] = total_fm
    return result


def speichere_mischfutter(misch_fm_id: int, komponenten: list) -> None:
    """
    Ersetzt die Komponenten einer Mischung.
    komponenten: list of (fm_id: int, anteil_kg: float)
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM mischfuttermittel_komponenten WHERE misch_fm_id=?",
            (misch_fm_id,))
        for sort_i, (fm_id, anteil_kg) in enumerate(komponenten):
            conn.execute(
                "INSERT INTO mischfuttermittel_komponenten "
                "(misch_fm_id, komponente_fm_id, anteil_kg, sort_order) VALUES (?,?,?,?)",
                (misch_fm_id, fm_id, anteil_kg, sort_i))


def lade_mischfutter_komponenten(misch_fm_id: int) -> list:
    """
    Gibt alle Komponenten einer Mischung zurück (fm-Daten + '_anteil_kg').
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT mk.anteil_kg, f.*
            FROM mischfuttermittel_komponenten mk
            JOIN futtermittel f ON mk.komponente_fm_id = f.id
            WHERE mk.misch_fm_id = ?
            ORDER BY mk.sort_order
            """,
            (misch_fm_id,)).fetchall()
    return [{**dict(r), "_anteil_kg": r["anteil_kg"]} for r in rows]


def _create_tables(conn: sqlite3.Connection):
    conn.executescript("""
    -- ============================================================
    -- KUNDEN & PFERDE
    -- ============================================================
    CREATE TABLE IF NOT EXISTS kunden (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        adresse     TEXT,
        telefon     TEXT,
        email       TEXT,
        erstellt_am TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS pferde (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        kunde_id        INTEGER NOT NULL REFERENCES kunden(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        gewicht_kg      REAL NOT NULL,
        alter_jahre     REAL NOT NULL,
        rasse_typ       TEXT NOT NULL DEFAULT 'Warmblut',
            -- Warmblut | Pony | Kaltblut | Vollblut
        nutzung         TEXT NOT NULL DEFAULT 'Freizeit',
            -- Freizeit | Leichte_Arbeit | Mittlere_Arbeit | Schwere_Arbeit
        geschlecht      TEXT DEFAULT 'Stute',
            -- Stute | Hengst | Wallach
        traechtigkeit   INTEGER DEFAULT 0,   -- 0=nein, 1..11 = Monat der Trächtigkeit
        laktation       INTEGER DEFAULT 0,   -- 0=nein, 1..6 = Laktationsmonat
        diagnosen       TEXT DEFAULT '',
            -- kommasepariert: EMS, Cushing, PSSM1, PSSM2, MIM
        notiz           TEXT,
        erstellt_am     TEXT DEFAULT (datetime('now')),
        geaendert_am    TEXT DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- FUTTERMITTEL
    -- ============================================================
    CREATE TABLE IF NOT EXISTS futtermittel (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        name                    TEXT NOT NULL,
        hersteller              TEXT,
        kategorie               TEXT NOT NULL,
            -- Raufutter | Kraftfutter | Ergaenzungsfutter | Mineralfutter
            -- Rohstoff | Heu
        produkt_typ             TEXT,
            -- z.B. Müsli | Pellets | Flakes | Mineral | Heu_Wiese | Heu_Gras etc.
        wassergehalt_pct        REAL DEFAULT 12.0,
            -- Standard 12%, manuell überschreibbar
        -- Energie & Hauptnährstoffe (je kg Trockenmasse)
        energie_mj_me           REAL,   -- MJ metabolisierbare Energie
        rohprotein_pct          REAL,   -- %
        lysin_g                 REAL,   -- g
        methionin_g             REAL,   -- g
        rohfett_pct             REAL,   -- %
        rohfaser_pct            REAL,   -- %
        staerke_pct             REAL,   -- %
        zucker_pct              REAL,   -- %
        nsc_pct                 REAL,   -- Stärke + Zucker zusammen
        -- Makromineralien (g/kg TS)
        calcium_g               REAL,
        phosphor_g              REAL,
        magnesium_g             REAL,
        natrium_g               REAL,
        kalium_g                REAL,
        -- Spurenelemente (mg/kg TS)
        eisen_mg                REAL,
        kupfer_mg               REAL,
        zink_mg                 REAL,
        mangan_mg               REAL,
        selen_mg                REAL,
        jod_mg                  REAL,
        kobalt_mg               REAL,
        -- Vitamine (IE oder mg/kg TS)
        vit_a_ie                REAL,
        vit_d_ie                REAL,
        vit_e_mg                REAL,
        vit_b1_mg               REAL,
        biotin_mcg              REAL,
        -- Metadaten
        quelle                  TEXT,   -- Herstellerangabe | DLG | GfE | Eigeneingabe | OCR
        anlagedatum             TEXT DEFAULT (datetime('now')),
        aenderungsdatum         TEXT DEFAULT (datetime('now')),
        version                 INTEGER DEFAULT 1,
        aktiv                   INTEGER DEFAULT 1
    );

    -- ============================================================
    -- HEU-QUALITÄTSSTUFEN (Stammdaten)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS heu_qualitaet (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        bezeichnung TEXT NOT NULL,   -- Sehr gut | Gut | Mittel | Gering | Sehr gering
        energie_min REAL,
        energie_max REAL,
        rp_min_pct  REAL,
        rp_max_pct  REAL,
        zucker_staerke_max_pct REAL,
        beschreibung TEXT
    );

    -- ============================================================
    -- RATIONEN
    -- ============================================================
    CREATE TABLE IF NOT EXISTS rationen (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        pferd_id        INTEGER NOT NULL REFERENCES pferde(id) ON DELETE CASCADE,
        bezeichnung     TEXT NOT NULL,
        erstellt_am     TEXT DEFAULT (datetime('now')),
        geaendert_am    TEXT DEFAULT (datetime('now')),
        notiz           TEXT,
        aktiv           INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS rations_positionen (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ration_id       INTEGER NOT NULL REFERENCES rationen(id) ON DELETE CASCADE,
        futtermittel_id INTEGER NOT NULL REFERENCES futtermittel(id),
        menge_kg        REAL NOT NULL,      -- Frischmasse in kg
        sort_order      INTEGER DEFAULT 0
    );

    -- ============================================================
    -- MISCHFUTTERMITTEL-REZEPTE
    -- ============================================================
    CREATE TABLE IF NOT EXISTS mischfuttermittel_komponenten (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        misch_fm_id         INTEGER NOT NULL REFERENCES futtermittel(id) ON DELETE CASCADE,
        komponente_fm_id    INTEGER NOT NULL REFERENCES futtermittel(id),
        anteil_kg           REAL NOT NULL,   -- kg Frischmasse pro definierter "Charge"
        sort_order          INTEGER DEFAULT 0
    );

    -- ============================================================
    -- BEDARFSWERTE (berechnet, zur Anzeige gespeichert)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS bedarfswerte (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        pferd_id    INTEGER NOT NULL REFERENCES pferde(id) ON DELETE CASCADE,
        datum       TEXT DEFAULT (datetime('now')),
        energie_mj  REAL,
        rp_g        REAL,
        lysin_g     REAL,
        calcium_g   REAL,
        phosphor_g  REAL,
        magnesium_g REAL,
        natrium_g   REAL,
        kupfer_mg   REAL,
        zink_mg     REAL,
        mangan_mg   REAL,
        selen_mg    REAL,
        vit_e_mg    REAL,
        nsc_max_pct REAL     -- Limit bei EMS/Cushing/PSSM
    );
    """)


def _seed_stammdaten(conn: sqlite3.Connection):
    """Befüllt Heu-Qualitäten und Basis-Futtermittel falls Tabellen leer sind."""

    # Heu-Qualitätsstufen (GfE / DLG-Richtwerte)
    if conn.execute("SELECT COUNT(*) FROM heu_qualitaet").fetchone()[0] == 0:
        heu_data = [
            ("Sehr gut",     9.0, 9.5, 12.0, 15.0, 8.0,
             "Früh geschnitten, grüne Farbe, aromatisch"),
            ("Gut",          8.5, 9.0, 10.0, 13.0, 10.0,
             "Normales Wiesenheu, gute Qualität"),
            ("Mittel",       8.0, 8.5,  9.0, 11.0, 12.0,
             "Durchschnittliches Heu, leicht verholzt"),
            ("Gering",       7.0, 8.0,  7.0,  9.0, 14.0,
             "Spät geschnitten, hoher Ligningehalt"),
            ("Sehr gering",  6.0, 7.0,  5.0,  7.0, 16.0,
             "Strohähnlich, sehr verholzt"),
        ]
        conn.executemany(
            """INSERT INTO heu_qualitaet
               (bezeichnung, energie_min, energie_max, rp_min_pct, rp_max_pct,
                zucker_staerke_max_pct, beschreibung)
               VALUES (?,?,?,?,?,?,?)""",
            heu_data
        )

    # Basis-Rohstoffe (naturbelassene Produkte, gut dokumentiert)
    if conn.execute("SELECT COUNT(*) FROM futtermittel").fetchone()[0] == 0:
        jetzt = datetime.now().isoformat()
        rohstoffe = [
            # name, hersteller, kategorie, typ, wasser%,
            # energie, rp%, lysin_g, meth_g, fett%, faser%, staerke%, zucker%, nsc%,
            # Ca_g, P_g, Mg_g, Na_g, K_g, Fe_mg, Cu_mg, Zn_mg, Mn_mg, Se_mg, J_mg,
            # VitA, VitD, VitE, B1, Biotin, quelle
            ("Sonnenblumenkerne (geschält)", None, "Rohstoff", "Ölsaat", 6.0,
             19.6, 22.0, 7.2, 5.5, 52.0, 12.0, 4.0, 2.0, 6.0,
             3.5, 6.0, 3.4, 0.3, 6.7, 60, 20, 55, 22, 0.07, 0.05,
             0, 0, 35, 1.8, 0, "DLG-Futterwerttabelle"),

            ("Futterhanf (Samen)", None, "Rohstoff", "Ölsaat", 7.0,
             20.0, 25.0, 9.0, 5.0, 32.0, 22.0, 3.0, 2.0, 5.0,
             2.0, 8.0, 5.0, 0.2, 8.0, 80, 10, 70, 120, 0.06, 0.1,
             0, 0, 20, 0.5, 0, "Fachliteratur"),

            ("Weizen (gequetscht)", None, "Rohstoff", "Getreide", 12.0,
             13.5, 13.0, 4.0, 1.8, 2.0, 3.0, 64.0, 3.5, 67.5,
             0.7, 3.5, 1.2, 0.05, 4.0, 60, 5, 35, 55, 0.05, 0.05,
             0, 0, 12, 4.0, 0, "DLG-Futterwerttabelle"),

            ("Gerste (gequetscht)", None, "Rohstoff", "Getreide", 12.0,
             13.0, 12.0, 3.5, 1.7, 2.5, 5.0, 57.0, 2.5, 59.5,
             0.6, 3.6, 1.1, 0.07, 5.0, 60, 6, 36, 18, 0.04, 0.05,
             0, 0, 10, 3.5, 0, "DLG-Futterwerttabelle"),

            ("Hafer (gequetscht)", None, "Rohstoff", "Getreide", 12.0,
             12.5, 11.5, 4.2, 1.6, 5.5, 11.0, 40.0, 1.5, 41.5,
             1.0, 3.7, 1.2, 0.08, 4.5, 90, 6, 35, 40, 0.07, 0.05,
             0, 0, 10, 3.5, 0, "DLG-Futterwerttabelle"),

            ("Leinsamen (geschrotet)", None, "Rohstoff", "Ölsaat", 8.0,
             21.0, 22.0, 8.0, 4.0, 38.0, 8.0, 2.0, 1.5, 3.5,
             2.5, 6.0, 5.0, 0.3, 7.0, 50, 10, 45, 35, 0.08, 0.1,
             0, 0, 5, 0.6, 0, "DLG-Futterwerttabelle"),

            ("Karotten (frisch)", None, "Rohstoff", "Gemüse", 88.0,
             11.0, 8.0, 3.0, 1.0, 1.5, 10.0, 2.0, 7.0, 9.0,
             4.0, 2.5, 1.8, 0.5, 25.0, 30, 5, 25, 15, 0.05, 0.05,
             10000, 50, 5, 0.6, 0, "DLG-Futterwerttabelle"),
        ]
        conn.executemany(
            """INSERT INTO futtermittel
               (name, hersteller, kategorie, produkt_typ, wassergehalt_pct,
                energie_mj_me, rohprotein_pct, lysin_g, methionin_g,
                rohfett_pct, rohfaser_pct, staerke_pct, zucker_pct, nsc_pct,
                calcium_g, phosphor_g, magnesium_g, natrium_g, kalium_g,
                eisen_mg, kupfer_mg, zink_mg, mangan_mg, selen_mg, jod_mg,
                vit_a_ie, vit_d_ie, vit_e_mg, vit_b1_mg, biotin_mcg, quelle)
               VALUES (?,?,?,?,?, ?,?,?,?,?,?,?,?,?, ?,?,?,?,?,
                       ?,?,?,?,?,?, ?,?,?,?,?,?)""",
            rohstoffe
        )


def _seed_markenfuttermittel(conn: sqlite3.Connection):
    """
    Fügt Marken-Futtermittel ein, die noch nicht in der DB sind (anhand Name+Hersteller).
    Werte (Agrobs) von Herstellerwebsite, Stand 07/2025, umgerechnet auf kg TS (÷ 0,88 bei 12% Wasser).
    St. Hippolyt / WES: Inhaltsstoffe werden via JS geladen → Werte manuell zu ergänzen.
    """

    def _exists(name: str, hersteller: str) -> bool:
        row = conn.execute(
            "SELECT id FROM futtermittel WHERE name=? AND hersteller=? LIMIT 1",
            (name, hersteller)
        ).fetchone()
        return row is not None

    jetzt = datetime.now().isoformat()

    # ------------------------------------------------------------------
    # INSERT-Hilfe: 31 Felder (ohne id/anlagedatum/aenderungsdatum/version/aktiv)
    # Reihenfolge: name, hersteller, kategorie, produkt_typ, wassergehalt_pct,
    #   energie_mj_me, rohprotein_pct, lysin_g, methionin_g,
    #   rohfett_pct, rohfaser_pct, staerke_pct, zucker_pct, nsc_pct,
    #   calcium_g, phosphor_g, magnesium_g, natrium_g, kalium_g,
    #   eisen_mg, kupfer_mg, zink_mg, mangan_mg, selen_mg, jod_mg,
    #   vit_a_ie, vit_d_ie, vit_e_mg, vit_b1_mg, biotin_mcg, quelle
    # ------------------------------------------------------------------
    INSERT_SQL = """INSERT INTO futtermittel
        (name, hersteller, kategorie, produkt_typ, wassergehalt_pct,
         energie_mj_me, rohprotein_pct, lysin_g, methionin_g,
         rohfett_pct, rohfaser_pct, staerke_pct, zucker_pct, nsc_pct,
         calcium_g, phosphor_g, magnesium_g, natrium_g, kalium_g,
         eisen_mg, kupfer_mg, zink_mg, mangan_mg, selen_mg, jod_mg,
         vit_a_ie, vit_d_ie, vit_e_mg, vit_b1_mg, biotin_mcg, quelle)
        VALUES (?,?,?,?,?, ?,?,?,?,?,?,?,?,?, ?,?,?,?,?,
                ?,?,?,?,?,?, ?,?,?,?,?,?)"""

    # ==================================================================
    # AGROBS – Nährstoffe je kg TS (umgerechnet aus % FM ÷ 0,88)
    #          Quelle: agrobs.de Produktseiten, Stand 07/2025
    #          Wasser: 12 % (warmluftgetrocknet, Herstellerangabe)
    # ==================================================================

    agrobs = [
        # ---- PRE ALPIN Wiesencobs -----------------------------------------
        # FM-Basis: RP 8,80 | RFett 2,30 | RF 26,30 | RA 7,40 | ME 6,90
        #           Stärke 2,50 | Zucker 9,90 | Ca 0,60 | P 0,20 | Na 0,03
        ("PRE ALPIN Wiesencobs®", "Agrobs", "Raufutter", "Heucobs", 12.0,
         7.84, 10.00, None, None,
         2.61, 29.89, 2.84, 11.25, 14.09,
         6.82, 2.27, None, 0.34, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- PRE ALPIN Wiesenflakes® --------------------------------------
        # FM-Basis: RP 8,20 | RFett 1,90 | RF 25,50 | RA 9,00 | ME 6,60
        #           Stärke 1,90 | Zucker 9,50 | Ca 0,50 | P 0,20 | Na 0,03
        ("PRE ALPIN Wiesenflakes®", "Agrobs", "Raufutter", "Flakes", 12.0,
         7.50, 9.32, None, None,
         2.16, 28.98, 2.16, 10.80, 12.95,
         5.68, 2.27, None, 0.34, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- PRE ALPIN Senior ---------------------------------------------
        # FM-Basis: RP 7,40 | RFett 1,90 | RF 27,40 | RA 8,30 | ME 6,70
        #           Stärke 1,90 | Zucker 9,90 | Ca 0,60 | P 0,20 | Na 0,03
        ("PRE ALPIN Senior", "Agrobs", "Raufutter", "Flakes", 12.0,
         7.61, 8.41, None, None,
         2.16, 31.14, 2.16, 11.25, 13.41,
         6.82, 2.27, None, 0.34, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- AlpenGrün Müsli ---------------------------------------------
        # FM-Basis: RP 10,70 | RFett 5,50 | RF 23,10 | RA 6,50 | ME 8,60
        #           Stärke 2,00 | Zucker 8,70 | Ca 0,50 | P 0,30 | Na 0,05
        ("AlpenGrün Müsli", "Agrobs", "Kraftfutter", "Müsli", 12.0,
         9.77, 12.16, None, None,
         6.25, 26.25, 2.27, 9.89, 12.16,
         5.68, 3.41, None, 0.57, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- MYO Protein Flakes ------------------------------------------
        # FM-Basis: RP 12,40 | RFett 2,80 | RF 21,30 | RA 10,00 | ME 6,50
        #           Stärke 2,10 | Zucker 6,30 | Ca 0,80 | P 0,30 | Na 0,05
        ("MYO Protein Flakes", "Agrobs", "Kraftfutter", "Flakes", 12.0,
         7.39, 14.09, None, None,
         3.18, 24.20, 2.39, 7.16, 9.55,
         9.09, 3.41, None, 0.57, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- PRE ALPIN Protein Light Flakes -------------------------------
        # FM-Basis: RP 5,10 | RFett 1,50 | RF 31,30 | RA 2,20 | ME 6,90
        #           Stärke 5,70 | Zucker 16,10 | Ca 0,20 | P 0,20 | Na 0,01
        # Hinweis: hoher Zucker+Stärke → NSC 24,8% → NICHT für EMS/Cushing!
        ("PRE ALPIN Protein Light Flakes", "Agrobs", "Raufutter", "Flakes", 12.0,
         7.84, 5.80, None, None,
         1.70, 35.57, 6.48, 18.30, 24.77,
         2.27, 2.27, None, 0.11, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- Luzernecobs -------------------------------------------------
        # FM-Basis: RP 14,40 | RFett 1,90 | RF 29,40 | RA 8,80 | ME 5,60
        #           Stärke 2,10 | Zucker 2,90 | Ca 1,30 | P 0,30 | Na 0,01
        ("Luzernecobs", "Agrobs", "Raufutter", "Heucobs", 12.0,
         6.36, 16.36, None, None,
         2.16, 33.41, 2.39, 3.30, 5.68,
         14.77, 3.41, None, 0.11, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),
    ]

    for eintrag in agrobs:
        if not _exists(eintrag[0], eintrag[1]):
            conn.execute(INSERT_SQL, eintrag)

    # ==================================================================
    # ST. HIPPOLYT / WES – Platzhalter (Inhaltsstoffe via JS, nicht abrufbar)
    #   → Nährstoffe bitte manuell über die Futtermittel-Ansicht eintragen
    #     (Werte stehen auf dem Sack / Etikett)
    # ==================================================================

    hippolyt_platzhalter = [
        # Ergänzungsfuttermittel – getreide- und melassefrei, stärke-/zuckerreduziert
        ("Glyx-Mash®", "St. Hippolyt", "Ergaenzungsfutter", "Mash", 12.0,
         None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Bitte Nährstoffe vom Etikett eintragen (st-hippolyt.de)"),

        # Mineral- & Muskelaufbaufutter für PSSM1/MIM/RER – ohne Soja/Getreide/Luzerne
        ("WES Sensitive Bodyguard", "St. Hippolyt / WES", "Mineralfutter", "Mineral", 12.0,
         None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Bitte Nährstoffe vom Etikett eintragen (st-hippolyt.de)"),

        # Spurenelement- und Vitaminbooster (organisch gebundene Spurenelemente)
        ("MicroVital®", "St. Hippolyt", "Mineralfutter", "Mineral", 12.0,
         None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Bitte Nährstoffe vom Etikett eintragen (st-hippolyt.de)"),

        # Häckselheu für Senioren / Zahnprobleme; 1 kg ersetzt 1 kg Heu
        # Werte: Schätzung auf Basis Wiesenheuprofil + Niedrig-NSC-Charakteristik
        # (St. Hippolyt Website: Inhaltsstoffe via JS – bitte bei Gelegenheit prüfen)
        ("GlyxWiese\u00ae Seniorfaser", "St. Hippolyt", "Raufutter", "Fasern", 10.0,
         7.0,  9.0,  None, None,
         2.5,  30.0, 1.5,  6.5,  8.0,
         6.0,  2.5,  1.5,  0.3,  None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Sch\u00e4tzwert Heu-Basis, niedrig-NSC (GlyxWiese\u00ae-Serie) \u2013 bitte vom Etikett pr\u00fcfen"),
    ]

    for eintrag in hippolyt_platzhalter:
        if not _exists(eintrag[0], eintrag[1]):
            conn.execute(INSERT_SQL, eintrag)

    # ==================================================================
    # ROHSTOFFE (Öle / Fette)
    # ==================================================================
    oele = [
        # Rapsöl – GfE 2014, Tabelle Einzelfuttermittel für Pferde
        # ~99 % Rohfett, nahezu keine Stärke/Zucker, ME 34,3 MJ/kg TS
        ("Raps\u00f6l", None, "Rohstoff", "\u00d6l", 0.0,
         34.3, 0.0,  None, None,
         99.0, 0.0,  0.0,  0.0,  0.0,
         0.0,  0.0,  0.0,  0.0,  None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "GfE 2014 (Gesellschaft f\u00fcr Ern\u00e4hrungsphysiologie)"),
    ]

    for eintrag in oele:
        if not _exists(eintrag[0], eintrag[1]):
            conn.execute(INSERT_SQL, eintrag)




def alle_futtermittel(kategorie: str = None) -> list:
    with get_connection() as conn:
        if kategorie:
            rows = conn.execute(
                "SELECT * FROM futtermittel WHERE aktiv=1 AND kategorie=? ORDER BY name",
                (kategorie,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM futtermittel WHERE aktiv=1 ORDER BY kategorie, name"
            ).fetchall()
    return [dict(r) for r in rows]


def alle_kunden() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM kunden ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def pferde_von_kunde(kunde_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pferde WHERE kunde_id=? ORDER BY name", (kunde_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def heu_qualitaeten() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM heu_qualitaet ORDER BY energie_max DESC").fetchall()
    return [dict(r) for r in rows]


def speichere_ist_schema(pferd_id: int,
                         heu_qualitaet_id: int | None,
                         heu_menge_kg: float,
                         positionen: list) -> int:
    """
    Speichert die aktuelle Ration als 'Ist-Schema' für das Pferd (ersetzt evtl. vorhandenes).
    positionen: list of (futtermittel_id: int, menge_kg: float)
    Returns: neue ration_id
    """
    with get_connection() as conn:
        # Altes Ist-Schema dieses Pferds entfernen
        conn.execute(
            "DELETE FROM rationen WHERE pferd_id=? AND bezeichnung='Ist-Schema'",
            (pferd_id,))
        # Neues Schema anlegen
        cursor = conn.execute(
            """
            INSERT INTO rationen (pferd_id, bezeichnung, heu_qualitaet_id, heu_menge_kg,
                                  erstellt_am, geaendert_am)
            VALUES (?, 'Ist-Schema', ?, ?, datetime('now'), datetime('now'))
            """,
            (pferd_id, heu_qualitaet_id, heu_menge_kg))
        ration_id = cursor.lastrowid
        for sort_i, (fm_id, menge) in enumerate(positionen):
            conn.execute(
                "INSERT INTO rations_positionen "
                "(ration_id, futtermittel_id, menge_kg, sort_order) VALUES (?,?,?,?)",
                (ration_id, fm_id, menge, sort_i))
        return ration_id


def lade_ist_schema(pferd_id: int) -> dict | None:
    """
    Lädt das gespeicherte Ist-Schema für ein Pferd.
    Returns dict mit keys 'ration', 'positionen' (list of fm-dicts + menge_kg),
    'heu' (heu_qualitaet-dict oder None)  –  oder None wenn kein Schema vorhanden.
    """
    with get_connection() as conn:
        ration = conn.execute(
            """
            SELECT r.* FROM rationen r
            WHERE r.pferd_id=? AND r.bezeichnung='Ist-Schema' AND r.aktiv=1
            ORDER BY r.geaendert_am DESC LIMIT 1
            """,
            (pferd_id,)).fetchone()
        if not ration:
            return None
        ration_dict = dict(ration)

        positionen_rows = conn.execute(
            """
            SELECT rp.menge_kg, f.*
            FROM rations_positionen rp
            JOIN futtermittel f ON rp.futtermittel_id = f.id
            WHERE rp.ration_id = ?
            ORDER BY rp.sort_order
            """,
            (ration_dict["id"],)).fetchall()

        heu = None
        if ration_dict.get("heu_qualitaet_id"):
            heu = conn.execute(
                "SELECT * FROM heu_qualitaet WHERE id=?",
                (ration_dict["heu_qualitaet_id"],)).fetchone()

        return {
            "ration":     ration_dict,
            "positionen": [
                {**dict(r), "_menge_kg": r["menge_kg"]} for r in positionen_rows
            ],
            "heu": dict(heu) if heu else None,
        }


def speichere_futtermittel(daten: dict) -> int:
    """Fügt ein neues Futtermittel ein oder aktualisiert es. Gibt die ID zurück."""
    daten["aenderungsdatum"] = datetime.now().isoformat()
    if "id" in daten and daten["id"]:
        daten["version"] = daten.get("version", 1) + 1
        felder = [k for k in daten if k != "id"]
        sql = f"UPDATE futtermittel SET {', '.join(f'{f}=?' for f in felder)} WHERE id=?"
        with get_connection() as conn:
            conn.execute(sql, [daten[f] for f in felder] + [daten["id"]])
        return daten["id"]
    else:
        daten.setdefault("anlagedatum", datetime.now().isoformat())
        felder = [k for k in daten if k != "id"]
        sql = f"INSERT INTO futtermittel ({', '.join(felder)}) VALUES ({', '.join('?' * len(felder))})"
        with get_connection() as conn:
            cur = conn.execute(sql, [daten[f] for f in felder])
            return cur.lastrowid


def speichere_pferd(daten: dict) -> int:
    daten["geaendert_am"] = datetime.now().isoformat()
    if "id" in daten and daten["id"]:
        felder = [k for k in daten if k != "id"]
        sql = f"UPDATE pferde SET {', '.join(f'{f}=?' for f in felder)} WHERE id=?"
        with get_connection() as conn:
            conn.execute(sql, [daten[f] for f in felder] + [daten["id"]])
        return daten["id"]
    else:
        daten.setdefault("erstellt_am", datetime.now().isoformat())
        felder = [k for k in daten if k != "id"]
        sql = f"INSERT INTO pferde ({', '.join(felder)}) VALUES ({', '.join('?' * len(felder))})"
        with get_connection() as conn:
            cur = conn.execute(sql, [daten[f] for f in felder])
            return cur.lastrowid


def speichere_kunden(daten: dict) -> int:
    if "id" in daten and daten["id"]:
        felder = [k for k in daten if k != "id"]
        sql = f"UPDATE kunden SET {', '.join(f'{f}=?' for f in felder)} WHERE id=?"
        with get_connection() as conn:
            conn.execute(sql, [daten[f] for f in felder] + [daten["id"]])
        return daten["id"]
    else:
        felder = [k for k in daten if k != "id"]
        sql = f"INSERT INTO kunden ({', '.join(felder)}) VALUES ({', '.join('?' * len(felder))})"
        with get_connection() as conn:
            cur = conn.execute(sql, [daten[f] for f in felder])
            return cur.lastrowid
