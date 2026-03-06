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
        # Migration: bevorzugt-Spalte in supplement_katalog
        try:
            conn.execute("ALTER TABLE supplement_katalog ADD COLUMN bevorzugt INTEGER DEFAULT 0")
        except Exception:
            pass  # bereits vorhanden
        # Migration: pferde — individuelle Bedarfs-Overrides und Raufutter-Minimum
        for col, typ in [
            ("override_energie_mj",  "REAL"),
            ("override_begruendung", "TEXT"),
            ("raufutter_min_kg",     "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE pferde ADD COLUMN {col} {typ}")
            except Exception:
                pass
        # Migration: rationen — Verlust und Mahlzeiten
        for col, typ in [
            ("heu_mahlzeiten",  "INTEGER DEFAULT 2"),
            ("heu_verlust_pct", "REAL DEFAULT 0.0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE rationen ADD COLUMN {col} {typ}")
            except Exception:
                pass
        # Testdatensätze bereinigen
        conn.execute("DELETE FROM futtermittel WHERE name LIKE '__TEST%'")
        _seed_stammdaten(conn)
        _seed_markenfuttermittel(conn)
        _seed_supplement_katalog(conn)           # Erstbefüllung
        _migrate_supplement_katalog(conn)        # Neue Einträge in bestehende DBs einpflegen
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

    -- ============================================================
    -- SUPPLEMENT-KATALOG (reine Einzelsubstanzen)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS supplement_katalog (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        name                    TEXT NOT NULL,
        typ                     TEXT NOT NULL,
            -- Spurenelement | Vitamin | Aminosäure | Makromineral | Fettsäure
        naehr_feld              TEXT NOT NULL,
            -- Feldname in RationsErgebnis/Bedarfswerte, z.B. 'selen_mg', 'lysin_g'
        einheit                 TEXT NOT NULL,
            -- mg | g | IE | mcg  (Einheit des Wirkstoffs)
        konzentration_je_kg     REAL NOT NULL,
            -- Menge Wirkstoff (in 'einheit') pro kg Supplement
        max_tagesdosis_einheit  REAL,
            -- empfohlene Max-Tagesdosis in der Wirkstoff-Einheit
        bevorzugt               INTEGER DEFAULT 0,
            -- 1 = empfohlene (org.) Form; 0 = alternative/anorganische Form
        hinweis                 TEXT,
        quelle                  TEXT DEFAULT 'Fachliteratur',
        aktiv                   INTEGER DEFAULT 1
    );

    -- ============================================================
    -- OPTIMIERUNGSVARIANTEN
    -- ============================================================
    CREATE TABLE IF NOT EXISTS optimierungs_variante (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        pferd_id        INTEGER NOT NULL REFERENCES pferde(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        beschreibung    TEXT,
        erstellt_am     TEXT DEFAULT (datetime('now')),
        geaendert_am    TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS variante_position (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        variante_id         INTEGER NOT NULL
                            REFERENCES optimierungs_variante(id) ON DELETE CASCADE,
        quell_typ           TEXT NOT NULL,
            -- 'futtermittel' | 'supplement' | 'heu'
        futtermittel_id     INTEGER REFERENCES futtermittel(id),
        supplement_id       INTEGER REFERENCES supplement_katalog(id),
        heu_qualitaet_id    INTEGER REFERENCES heu_qualitaet(id),
        menge_kg            REAL NOT NULL,
            -- Frischmasse kg; für Supplement: Dosis in g ÷ 1000
        sort_order          INTEGER DEFAULT 0
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

    Enthaltene Producto (Stand 07/2025):
     Agrobs (bestehend): PRE ALPIN Wiesencobs, Wiesenflakes, Senior, AlpenGrün Müsli,
                         MYO Protein Flakes, Protein Light Flakes, Luzernecobs
     Agrobs (neu):       Aspero, Bio Wiesencobs, AlpenGrün Mash, compact,
                         LeichtGenuss, AlpenHeu, Stroh, Luzerne+, Grünhafer
     St. Hippolyt:       Glyx-Mash (Platzhalter), WES Sensitive Bodyguard (Platzhalter),
                         MicroVital (Platzhalter), GlyxWiese Seniorfaser (Schätzwert)
     Rohstoffe:          Rapsöl
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
    # AGROBS – NEUE Produkte (Stand 07/2025, je kg TS, ÷ 0,88)
    # Alle Angaben wurden von den Einzelproduktseiten agrobs.de abgerufen.
    # ==================================================================
    agrobs_neu = [
        # ---- PRE ALPIN Aspero ------------------------------------------
        # FM: RP 5,30 | RFett 2,10 | RF 29,50 | ME 6,30 | Stk 1,80 | Zuk 7,40
        #     Ca 0,40 | P 0,20 | Na 0,02
        # Häcksel aus Wiesengräsern+Kräutern + Lein-/Leindotteröl; strukturreich
        ("PRE ALPIN Aspero", "Agrobs", "Raufutter", "Häcksel", 12.0,
         7.16,  6.02, None, None,
         2.39, 33.52, 2.05,  8.41, 10.45,
         4.55,  2.27, None,  0.23, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- PRE ALPIN Bio Wiesencobs® ---------------------------------
        # FM: RP 11,50 | RFett 2,70 | RF 25,00 | ME 6,60 | Stk 2,90 | Zuk 6,30
        #     Ca 0,70 | P 0,20 | Na 0,02
        # Bio-zertifiziert (DE-ÖKO); gleiche Wiesen wie konventionell, BIO-Qualität
        ("PRE ALPIN Bio Wiesencobs\u00ae", "Agrobs", "Raufutter", "Heucobs", 12.0,
         7.50, 13.07, None, None,
         3.07, 28.41, 3.30,  7.16, 10.45,
         7.95,  2.27, None,  0.23, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- AlpenGrün Mash --------------------------------------------
        # FM: RP 12,70 | RFett 3,60 | RF 20,80 | ME 8,10 | Stk 1,70 | Zuk 9,50
        #     Ca 0,50 | P 0,30 | Na 0,05
        # Darmgesundheit/Prebiotik; getreidefrei, tägl. geeignet; Ca:P ≈ 2:1
        ("AlpenGr\u00fcn Mash", "Agrobs", "Kraftfutter", "Mash", 12.0,
         9.20, 14.43, None, None,
         4.09, 23.64, 1.93, 10.80, 12.73,
         5.68,  3.41, None,  0.57, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- PRE ALPIN compact -----------------------------------------
        # FM: RP 7,10 | RFett 1,80 | RF 27,40 | ME 6,50 | Stk 1,90 | Zuk 10,60
        #     Ca 0,50 | P 0,22 | Na 0,02
        # Gepresste Quader (14×16×8 cm); für unterwegs/Turniere; melassefrei
        ("PRE ALPIN compact", "Agrobs", "Raufutter", "Heucobs", 12.0,
         7.39,  8.07, None, None,
         2.05, 31.14, 2.16, 12.05, 14.20,
         5.68,  2.50, None,  0.23, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- LeichtGenuss ----------------------------------------------
        # FM: RP 9,30 | RFett 2,10 | RF 28,70 | ME 6,40 | Stk 2,00 | Zuk 8,20
        #     Ca 0,50 | P 0,30 | Na 0,03
        # Für EMS/PPID/Übergewicht; Grünhafer+Stroh+Wiesengräser; energiearm
        ("LeichtGenuss", "Agrobs", "Raufutter", "H\u00e4cksel", 12.0,
         7.27, 10.57, None, None,
         2.39, 32.61, 2.27,  9.32, 11.59,
         5.68,  3.41, None,  0.34, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- AlpenHeu --------------------------------------------------
        # FM: RP 6,40 | RFett 1,60 | RF 28,50 | ME 6,10 | Stk 1,80 | Zuk 6,00
        #     Ca 0,30 | P 0,20 | Na 0,02
        # Warmluft+sonnengetrocknet; entstaubt; bis 15 cm Faserlänge
        ("AlpenHeu", "Agrobs", "Raufutter", "Heu", 12.0,
         6.93,  7.27, None, None,
         1.82, 32.39, 2.05,  6.82,  8.86,
         3.41,  2.27, None,  0.23, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- Stroh (Agrobs) --------------------------------------------
        # FM: RP 2,50 | RFett 0,90 | RF 40,60 | ME 4,00 | Stk 2,00 | Zuk 3,00
        #     Ca 0,30 | P 0,06 | Na 0,01
        # Gersten-/Weizenstroh; warmluftgetrocknet+entstaubt; sehr eiweißarm
        ("Stroh", "Agrobs", "Raufutter", "Stroh", 12.0,
         4.55,  2.84, None, None,
         1.02, 46.14, 2.27,  3.41,  5.68,
         3.41,  0.68, None,  0.11, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- Luzerne+ --------------------------------------------------
        # FM: RP 10,00 | RFett 2,40 | RF 38,40 | ME 4,90 | Stk 2,00 | Zuk 5,60
        #     Ca 0,68 | P 0,25 | Na 0,02
        # Luzerne:Grünhafer 4:1; Leinöl; für Sportpferde/Aufbau; stärkarm
        ("Luzerne+", "Agrobs", "Raufutter", "H\u00e4cksel", 12.0,
         5.57, 11.36, None, None,
         2.73, 43.64, 2.27,  6.36,  8.64,
         7.73,  2.84, None,  0.23, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),

        # ---- Grünhafer -------------------------------------------------
        # FM: RP 12,50 | RFett 2,00 | RF 25,80 | ME 6,70 | Stk 2,00 | Zuk 5,80
        #     Ca 0,31 | P 0,35 | Na 0,04
        # Ganze Haferpflanze vor Stärkeeinlagerung; Getreideersatz; Ca:P ≈ 0,9
        ("Gr\u00fcnhafer", "Agrobs", "Raufutter", "H\u00e4cksel", 12.0,
         7.61, 14.20, None, None,
         2.27, 29.32, 2.27,  6.59,  8.86,
         3.52,  3.98, None,  0.45, None,
         None, None, None, None, None, None,
         None, None, None, None, None,
         "Herstellerangabe agrobs.de 07/2025"),
    ]

    for eintrag in agrobs_neu:
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


# ---------------------------------------------------------------------------
# Vollständige Supplement-Einträge (organisch bevorzugt, anorganisch als Option)
# Format: (name, typ, naehr_feld, einheit, konzentration_je_kg,
#           max_tagesdosis_einheit, bevorzugt, hinweis)
# ---------------------------------------------------------------------------
_ALLE_SUPPLEMENTE = [

    # ══════════════════════════════════════════════════════
    # SPURENELEMENTE
    # ══════════════════════════════════════════════════════

    # ── Selen ──
    ("Selenomethionin (Reinsubstanz, 99%)", "Spurenelement", "selen_mg", "mg",
     320_000.0, 3.0, 1,
     "L-Selenomethionin; org. Se-Form; Se-Gehalt ~32%; höchste Bioverfügbarkeit (>90%); "
     "wird in Muskelprotein eingebaut (Selenprotein P). GfE: 0,1–0,2 mg Se/kg KGW/Tag optimal. "
     "Einzige org. Se-Form, die §11 FuttMVV erfüllt. BEVORZUGT bei empfindlichen Pferden."),
    ("Selenhefe (organisch, 0,2% Se)", "Spurenelement", "selen_mg", "mg",
     2_000.0, 3.0, 1,
     "Selenreiche Backhefe; enthält Selenomethionin und andere org. Se-Verbindungen; "
     "gute Alternative zur Reinsubstanz; natürliche Matrix verbessert Verträglichkeit. "
     "Konzentration kann je nach Produkt 0,1–0,4% Se variieren – Etikett prüfen!"),
    ("Natriumselenit (97%, anorganisch)", "Spurenelement", "selen_mg", "mg",
     440_000.0, 3.0, 0,
     "NaSeO₃; Se-Gehalt ~45%; anorganisch; schnell verfügbar aber schlechtere Retention. "
     "Kann in höheren Dosierungen prooxidativ wirken. Nur wenn org. Formen nicht verfügbar. "
     "Toxische Breite eng: Bedarf ~2 mg/Tag, toxisch ab ~3–5 mg/Tag bei 500 kg Pferd."),
    ("Natriumselenat (anorganisch)", "Spurenelement", "selen_mg", "mg",
     415_000.0, 3.0, 0,
     "Na₂SeO₄; höhere intestinale Absorption als Selenit, aber noch anorganisch. "
     "Weniger gebräuchlich als Selenit. Toxizität ähnlich wie Selenit."),

    # ── Zink ──
    ("Zink-Bisglycinat (chelat, ~20% Zn)", "Spurenelement", "zink_mg", "mg",
     200_000.0, 1000.0, 1,
     "Zink-Aminosäure-Chelat (Zn-Glycinat); org. Form; bessere Absorption als Zinkoxid, "
     "weniger Antagonismus mit Cu und Fe. Empfohlen bei Hautproblemen, Hufhornqualität, "
     "Immunsystem. Mn:Zn-Ratio beachten (3:1 bis 4:1 empfohlen)."),
    ("Zinkcitrat (33% Zn)", "Spurenelement", "zink_mg", "mg",
     330_000.0, 1000.0, 1,
     "ZnC₁₂H₁₀O₁₄; gut wasserlöslich; mittlere Bioverfügbarkeit; "
     "gut verträglich, wird häufig in Humanpräparaten eingesetzt."),
    ("Zinksulfat-Monohydrat (35% Zn)", "Spurenelement", "zink_mg", "mg",
     350_000.0, 1000.0, 0,
     "ZnSO₄·H₂O; 35% Zn; günstig, aber höheres Risiko für Cu-Antagonismus. "
     "Kann bei dauerhafter Überdosierung zu sekundärem Kupfermangel führen."),
    ("Zinkoxid (80% Zn, lebensmittelqualität)", "Spurenelement", "zink_mg", "mg",
     803_000.0, 1000.0, 0,
     "ZnO; 80,3% Zn; schlechte Wasserlöslichkeit, niedrigste Bioverfügbarkeit der Zinkformen. "
     "Häufig in günstigen Mineralfuttern. Mn:Zn-Ratio (≈3:1) beachten."),

    # ── Kupfer ──
    ("Kupfer-Bisglycinat (chelat, ~20% Cu)", "Spurenelement", "kupfer_mg", "mg",
     200_000.0, 500.0, 1,
     "Cu-Aminosäure-Chelat; org. Form; deutlich bessere Bioverfügbarkeit als Sulfat, "
     "kaum Zink-Antagonismus. Empfohlen bei Fellpigmentierung, Hufqualität, Bindegewebe. "
     "EFSA max. 125 mg Cu/Tag für Equiden. Cave: Ponys/Weidegang/Leber-empfindliche Pferde."),
    ("Kupferproteinat (chelat, ~10–15% Cu)", "Spurenelement", "kupfer_mg", "mg",
     120_000.0, 500.0, 1,
     "Cu an Aminosäurehydrolysat gebunden; gute Bioverfügbarkeit; natürlichste Matrix. "
     "Konzentration je nach Produkt stark variabel – Etikett beachten."),
    ("Kupfersulfat-Pentahydrat (25% Cu)", "Spurenelement", "kupfer_mg", "mg",
     253_000.0, 500.0, 0,
     "CuSO₄·5H₂O; anorganisch; günstig aber starker Zink-Antagonist. "
     "Nicht empfohlen bei gleichzeitig hoher Zinkzufuhr. Überdosierung → Leberschaden."),

    # ── Mangan ──
    ("Mangan-Bisglycinat (chelat, ~15% Mn)", "Spurenelement", "mangan_mg", "mg",
     150_000.0, 2000.0, 1,
     "Mn-Aminosäure-Chelat; org. Form; bessere Absorption als Sulfat oder Oxid. "
     "Essenziell für Knorpelbildung (GAG-Synthese), Reproduktion und Enzymaktivität. "
     "Mn:Zn-Ratio anstreben: 3:1 bis 4:1."),
    ("Mangancitrat (29% Mn)", "Spurenelement", "mangan_mg", "mg",
     290_000.0, 2000.0, 1,
     "MnC₁₂H₁₀O₁₄; wasserlöslich; mittlere Bioverfügbarkeit; gute Verträglichkeit."),
    ("Mangan(II)-sulfat-Monohydrat (32% Mn)", "Spurenelement", "mangan_mg", "mg",
     324_000.0, 2000.0, 0,
     "MnSO₄·H₂O; 32,4% Mn; am häufigsten eingesetzt; anorganisch, aber akzeptable "
     "Bioverfügbarkeit im Gegensatz zu MnO."),
    ("Manganoxid (60% Mn)", "Spurenelement", "mangan_mg", "mg",
     600_000.0, 2000.0, 0,
     "MnO; schlechteste Bioverfügbarkeit aller Mn-Formen. Nicht empfohlen."),

    # ── Jod ──
    ("Kaliumjodid (76% J)", "Spurenelement", "jod_mg", "mg",
     760_000.0, 4.0, 1,
     "KI; 76% J; gut wasserlöslich; empfohlene Form für Equiden. "
     "Tagesbedarf ~2,5 mg J für 500 kg Pferd. EFSA max. 4 mg J/Tag. "
     "Cave: Schilddrüsenfunktion; sowohl Mangel als auch Überschuss problematisch."),
    ("Calciumjodat (65% J)", "Spurenelement", "jod_mg", "mg",
     650_000.0, 4.0, 0,
     "Ca(IO₃)₂; 65% J; weniger lichtempfindlich als KJ; in Mineralfuttern üblich. "
     "EFSA max. 4 mg J/Tag. Nicht empfohlen bei Schilddrüsenproblemen."),

    # ── Kobalt ──
    ("Kobalt(II)-carbonat (46% Co)", "Spurenelement", "kobalt_mg", "mg",
     460_000.0, 1.0, 0,
     "CoCO₃; 46% Co; Tagesbedarf ~0,5 mg; wird für Vitamin B12-Synthese im Darm benötigt. "
     "Max. 1 mg Co/Tag; Überschuss → Polyzythämie. Nur bei nachgewiesenem Mangel ergänzen."),
    ("Kobalt-Aminosäure-Chelat (~5% Co)", "Spurenelement", "kobalt_mg", "mg",
     50_000.0, 1.0, 1,
     "Cheliertes Kobalt; bessere Verträglichkeit als Carbonat; org. Form bevorzugt."),

    # ── Eisen ── (nur selten supplementieren, Überschuss häufiger als Mangel)
    ("Eisensulfat-Heptahydrat (20% Fe)", "Spurenelement", "eisen_mg", "mg",
     200_000.0, 500.0, 0,
     "FeSO₄·7H₂O; oft NICHT notwendig – Heu/Wasser liefern meist ausreichend Fe. "
     "Eisenüberschuss hemmt Kupfer- und Zink-Absorption. Nur bei dokumentiertem Mangel!"),

    # ══════════════════════════════════════════════════════
    # VITAMINE
    # ══════════════════════════════════════════════════════

    # ── Vitamin E ──
    ("Vitamin E natürlich (d-alpha-Tocopherol, 96%)", "Vitamin", "vit_e_mg", "mg",
     960_000.0, 5000.0, 1,
     "d-alpha-Tocopherol; natürliche Form; 2× höhere Bioverfügbarkeit als dl-alpha. "
     "GfE: 1–2 mg/kg KGW/Tag; bei PSSM/MIM/EDM/EMND: 3–5 mg/kg KGW/Tag empfohlen. "
     "Fettlöslich – nicht überdosieren, aber Toxizität beim Pferd gering bekannt."),
    ("Vitamin E (dl-alpha-Tocopherylacetat 50%)", "Vitamin", "vit_e_mg", "mg",
     500_000.0, 5000.0, 0,
     "dl-alpha-Tocopherylacetat; synthetisch; racemisches Gemisch; niedrigere Bioverfügbarkeit. "
     "Am häufigsten in Fertigpräparaten eingesetzt. Als Acetat stabiler gegenüber Oxidation."),
    ("Vitamin E wasserlöslich (d-alpha-Tocopherylsuccinat)", "Vitamin", "vit_e_mg", "mg",
     750_000.0, 5000.0, 1,
     "Succinat-Ester des natürl. Vit. E; wasserdispergierbar → bessere Absorption. "
     "Besonders bei Malabsorptionsproblemen oder für flüssige Formulierungen geeignet."),

    # ── Vitamin A ──
    ("Vitamin A (Beta-Carotin, 10% Pulver)", "Vitamin", "vit_a_ie", "IE",
     600_000.0, 30_000.0, 1,
     "Beta-Carotin als Vorstufe; wird vom Pferd bei Bedarf in Vit. A umgewandelt → "
     "kein Überdosierungsrisiko bei gesunder Leber! 10% = 100mg BC/g → ~10.000 IE/g. "
     "Natürliche Quelle: Frischgras/Karotten. Bei Stallhaltung oft mangelhaft."),
    ("Vitamin A (Retinylacetat, 500.000 IE/g)", "Vitamin", "vit_a_ie", "IE",
     500_000_000.0, 30_000.0, 0,
     "Retinylacetat; synthetisch; direkte Vit. A-Form. GfE: 60 IE/kg KGW/Tag. "
     "Max. 30.000 IE/Tag für 500 kg Pferd. Fettlöslich – Überdosierung möglich (Leber)!"),

    # ── Vitamin D ──
    ("Vitamin D3 (Cholecalciferol, 500.000 IE/g)", "Vitamin", "vit_d_ie", "IE",
     500_000_000.0, 6_600.0, 0,
     "Cholecalciferol; tierische Form; effektiver als D2 (Ergocalciferol). "
     "GfE: 6.600 IE/Tag für 500 kg Pferd. EFSA max. 44 IE/kg KGW/Tag. "
     "Sonneneinstrahlung + Trocknungsprozess bei Heu erzeugt D2 – "
     "Pferde mit Weidegang meist ausreichend versorgt."),

    # ── B-Vitamine ──
    ("Vitamin B1 (Thiaminhydrochlorid 99%)", "Vitamin", "vit_b1_mg", "mg",
     990_000.0, 200.0, 1,
     "Thiamin-HCl; wasserlöslich, keine bekannte Toxizität. "
     "Bei Stress, Schilfrohr-Fütterung (Goitrogene) oder Aderlassfarn-Vergiftung erhöhter Bedarf. "
     "Fördert Nervenfunktion, Kohlenhydratstoffwechsel."),
    ("Vitamin B2 (Riboflavin 98%)", "Vitamin", "vit_b1_mg", "mg",
     980_000.0, 100.0, 0,
     "Riboflavin; Energiestoffwechsel, Antioxidans-System (FAD). "
     "Meist ausreichend über Heu/Grünfutter gedeckt."),
    ("Biotin (D-Biotin, 1% Vormischung)", "Vitamin", "biotin_mcg", "mcg",
     10_000_000.0, 30_000.0, 1,
     "D-Biotin; 1% Konzentration → 10 mg Biotin/g Vormischung. "
     "Dosierung: 0,02–0,06 mg/kg KGW/Tag für Hufhorn; 15–30 mg/Tag typisch. "
     "Erste Effekte auf Hufhornqualität frühestens nach 6 Monaten sichtbar."),
    ("Biotin (D-Biotin 2%, Pellets)", "Vitamin", "biotin_mcg", "mcg",
     20_000_000.0, 30_000.0, 1,
     "D-Biotin 2%-Pellets; praxistaugliche Dosierung; 20 mg Biotin/g."),

    # ══════════════════════════════════════════════════════
    # AMINOSÄUREN
    # ══════════════════════════════════════════════════════

    ("L-Lysin-Monohydrochlorid (99%)", "Aminosäure", "lysin_g", "g",
     790.0, 60.0, 1,
     "L-Lysin·HCl; 79% Lysin; erstlimitierende Aminosäure beim Pferd. "
     "Defizite → eingeschränkter Muskelaufbau, schlechtere Immunantwort. "
     "Tagesbedarf ~junges Pferd: 45–70 g; Erhaltung: 25–40 g. Gut verträglich."),
    ("L-Methionin (99%)", "Aminosäure", "methionin_g", "g",
     990.0, 20.0, 1,
     "L-Methionin; schwefelhaltige AS; besser verwertbar als DL-Form. "
     "Wichtig für Hufhorn (Cystin/Keratin), Fell, Leber (Glutathion). "
     "Überdosierung vermeiden (>0,1 g/kg KGW/Tag): Methioninintoxikation möglich."),
    ("DL-Methionin (99%)", "Aminosäure", "methionin_g", "g",
     990.0, 20.0, 0,
     "DL-Methionin; synthetisch; racemisch; D-Form wird biologisch umgewandelt (beim Pferd "
     "weniger effizient als beim Geflügel). Günstiger als L-Form; meist in Fertigfuttern."),
    ("L-Threonin (99%)", "Aminosäure", "threonin_g", "g",
     990.0, 20.0, 1,
     "Threonin; drittlimitierende AS; wichtig für Mucin-Produktion (Darmschleimhaut), "
     "Immunsystem, Kollagensynthese. Besonders relevant bei hohem Grasanteil."),
    ("L-Tryptophan (98%)", "Aminosäure", "lysin_g", "g",
     980.0, 5.0, 1,
     "Tryptophan; Serotoninvorstufe; calming-Effekt bei nervösen Pferden (umstritten). "
     "Hinweis: Keine eigene DB-Spalte → wir erfassen es unter lysin_g als Orientierung. "
     "Cave: Einzelne Studien zeigen nur marginale Effekte auf Stressverhalten."),

    # ══════════════════════════════════════════════════════
    # MAKROMINERALIEN
    # ══════════════════════════════════════════════════════

    # ── Magnesium ──
    ("Magnesiumcitrat (16% Mg)", "Makromineral", "magnesium_g", "g",
     160.0, 30.0, 1,
     "MgC₁₂H₁₀O₁₄; organische Mg-Verbindung; sehr gute Bioverfügbarkeit; "
     "gut wasserlöslich; besonders empfohlen bei Nervosität, Muskelkrämpfen, "
     "Stressintoleranz. Sanfte Wirkung, sehr gut verträglich. BEVORZUGT."),
    ("Magnesium-Bisglycinat (chelat, ~14% Mg)", "Makromineral", "magnesium_g", "g",
     140.0, 30.0, 1,
     "Mg-Aminosäure-Chelat; höchste Bioverfügbarkeit; wird im Dünndarm aktiv absorbiert. "
     "Teuerste Form, aber kleinste Dosierung möglich. Ideal für empfindliche Pferde."),
    ("Magnesiumoxid (60% Mg)", "Makromineral", "magnesium_g", "g",
     603.0, 30.0, 0,
     "MgO; 60% Mg; günstigste Form, aber schlechteste Löslichkeit und Bioverfügbarkeit. "
     "Am häufigsten in Mineralfuttern eingesetzt; bei akutem Mangel ungeeignet."),
    ("Magnesiumchlorid-Hexahydrat (12% Mg)", "Makromineral", "magnesium_g", "g",
     120.0, 30.0, 0,
     "MgCl₂·6H₂O; 12% Mg; gut wasserlöslich; kann als Lösung verabreicht werden; "
     "hohe Cl-Zufuhr bei größeren Mengen beachten."),
    ("Magnesiumaspartat (8% Mg)", "Makromineral", "magnesium_g", "g",
     80.0, 30.0, 1,
     "Mg-L-Aspartat; gute Bioverfügbarkeit, wird im Energiestoffwechsel mitgenutzt. "
     "Besonders sinnvoll bei arbeitenden Pferden (Aspartat im Citrat-Zyklus)."),

    # ── Calcium ──
    ("Calciumcitrat (21% Ca)", "Makromineral", "calcium_g", "g",
     210.0, 80.0, 1,
     "Ca-Citrat; org. Form; Absorption unabhängig von Magensäure → günstiger bei "
     "älteren Pferden oder nach Protonenpumpenhemmer-Einsatz. "
     "Ca:P-Verhältnis nach Ergänzung prüfen (Ziel: 1,5:1 bis 2:1)."),
    ("Calciumcarbonat (Kreide, 40% Ca)", "Makromineral", "calcium_g", "g",
     400.0, 80.0, 0,
     "CaCO₃; günstig; benötigt Magensäure zur Absorption; "
     "am häufigsten eingesetzt. Cave: Ca:P-Ratio nach Supplementierung prüfen."),
    ("Dicalciumphosphat (23% Ca, 18% P)", "Makromineral", "calcium_g", "g",
     230.0, 80.0, 0,
     "CaHPO₄; deckt Ca UND P gleichzeitig; nützlich wenn beide defizitär. "
     "Ratio beachten: Ca:P sollte ≥ 1,5:1 bleiben."),

    # ── Phosphor ──
    ("Monokaliumphosphat (28% P)", "Makromineral", "phosphor_g", "g",
     280.0, 40.0, 0,
     "KH₂PO₄; 28% P; gut löslich; selten nötig (Heu meist P-ärmer als Ca, daher häufiger "
     "Ca supplementiert). Nur bei nachgewiesenem P-Defizit AND normalem Ca-Status einsetzen."),

    # ── Natrium ──
    ("Meersalz unraffiniert (38% Na)", "Makromineral", "natrium_g", "g",
     380.0, 50.0, 1,
     "NaCl + Spurenelemente; 38% Na; als Leckstein oder Pulver. "
     "Pferde regulieren Salzbedarf bei freiem Zugang selbst. "
     "Grundbedarf ~10–20 g NaCl/Tag; bei Arbeit und Hitze deutlich mehr."),
    ("Natriumchlorid (Kochsalz, 39% Na)", "Makromineral", "natrium_g", "g",
     393.0, 50.0, 0,
     "NaCl; 100% rein; günstig; kein Jod beim Pferd nötig, daher unjodiertes Salz bevorzugen."),

    # ══════════════════════════════════════════════════════
    # OMEGA-FETTSÄUREN / ÖLE (als Ergänzung)
    # ══════════════════════════════════════════════════════

    ("Leinöl kalt gepresst (omega-3-reich)", "Fettsäure", "rohfett_g", "g",
     9000.0, 200.0, 1,
     "Reichste ALA-Quelle (Alpha-Linolensäure = pflanzl. Omega-3); "
     "Anti-inflammatorisch, gut für Fellqualität, Hufhorn, Darmschleimhaut. "
     "30–100 ml/Tag praxisüblich (entspr. 27–90 g Fett). Täglich frisch verwenden."),
    ("Hanföl kalt gepresst (omega-3-/-6-balanced)", "Fettsäure", "rohfett_g", "g",
     9000.0, 200.0, 1,
     "Günstigstes Omega-3:Omega-6-Verhältnis aller Pflanzenöle (~3:1). "
     "Enthält GLA (Gamma-Linolensäure); entzündungshemmend. Cave: THC-Spuren möglich "
     "(EU-konformes Industriehanf <0,2% THC)."),
]


def _seed_supplement_katalog(conn: sqlite3.Connection):
    """Erstbefüllung des Supplement-Katalogs (nur wenn Tabelle leer)."""
    if conn.execute("SELECT COUNT(*) FROM supplement_katalog").fetchone()[0] > 0:
        return
    _insert_supplemente(conn, _ALLE_SUPPLEMENTE)


def _migrate_supplement_katalog(conn: sqlite3.Connection):
    """Fügt neue Einträge in bestehende DBs ein, ohne vorhandene zu duplizieren."""
    _insert_supplemente(conn, _ALLE_SUPPLEMENTE)


def _insert_supplemente(conn: sqlite3.Connection, eintraege: list):
    """Fügt Supplemente ein – überspringt bei doppeltem Namen."""
    for e in eintraege:
        name, typ, naehr_feld, einheit, konz, max_dos, bevorzugt, hinweis = e
        exists = conn.execute(
            "SELECT id FROM supplement_katalog WHERE name=?", (name,)
        ).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO supplement_katalog
                   (name, typ, naehr_feld, einheit, konzentration_je_kg,
                    max_tagesdosis_einheit, bevorzugt, hinweis)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (name, typ, naehr_feld, einheit, konz, max_dos, bevorzugt, hinweis),
            )


# ======================================================================
# SUPPLEMENT und VARIANTEN Datenzugriff
# ======================================================================

def alle_supplemente(typ: str = None) -> list:
    with get_connection() as conn:
        if typ:
            rows = conn.execute(
                "SELECT * FROM supplement_katalog WHERE aktiv=1 AND typ=?"
                " ORDER BY bevorzugt DESC, name",
                (typ,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM supplement_katalog WHERE aktiv=1"
                " ORDER BY typ, bevorzugt DESC, name"
            ).fetchall()
    return [dict(r) for r in rows]


def supplemente_fuer_feld(naehr_feld: str) -> list:
    """Gibt alle aktiven Supplemente zurück, die ein bestimmtes Nährstofffeld bedienen."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM supplement_katalog WHERE aktiv=1 AND naehr_feld=?"
            " ORDER BY bevorzugt DESC, name",
            (naehr_feld,),
        ).fetchall()
    return [dict(r) for r in rows]


def speichere_supplement(daten: dict) -> int:
    """INSERT oder UPDATE eines Supplements. Gibt die ID zurück."""
    with get_connection() as conn:
        if daten.get("id"):
            conn.execute(
                """
                UPDATE supplement_katalog
                   SET name=?, typ=?, naehr_feld=?, einheit=?,
                       konzentration_je_kg=?, max_tagesdosis_einheit=?,
                       bevorzugt=?, hinweis=?, quelle=?
                 WHERE id=?
                """,
                (
                    daten["name"], daten["typ"], daten["naehr_feld"], daten["einheit"],
                    daten["konzentration_je_kg"], daten.get("max_tagesdosis_einheit"),
                    daten.get("bevorzugt", 0), daten.get("hinweis"),
                    daten.get("quelle", "Eigene Eingabe"),
                    daten["id"],
                ),
            )
            return daten["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO supplement_katalog
                       (name, typ, naehr_feld, einheit, konzentration_je_kg,
                        max_tagesdosis_einheit, bevorzugt, hinweis, quelle)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    daten["name"], daten["typ"], daten["naehr_feld"], daten["einheit"],
                    daten["konzentration_je_kg"], daten.get("max_tagesdosis_einheit"),
                    daten.get("bevorzugt", 0), daten.get("hinweis"),
                    daten.get("quelle", "Eigene Eingabe"),
                ),
            )
            return cur.lastrowid


def loesche_supplement(supplement_id: int) -> None:
    """Deaktiviert ein Supplement (Soft-Delete, aktiv=0)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE supplement_katalog SET aktiv=0 WHERE id=?", (supplement_id,)
        )


def alle_varianten_fuer_pferd(pferd_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM optimierungs_variante WHERE pferd_id=? ORDER BY geaendert_am DESC",
            (pferd_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def lade_variante(variante_id: int) -> dict | None:
    """Lädt eine Variante inkl. aller Positionen."""
    with get_connection() as conn:
        var = conn.execute(
            "SELECT * FROM optimierungs_variante WHERE id=?", (variante_id,)
        ).fetchone()
        if not var:
            return None
        positionen = conn.execute(
            "SELECT * FROM variante_position WHERE variante_id=? ORDER BY sort_order",
            (variante_id,),
        ).fetchall()
    return {
        "variante": dict(var),
        "positionen": [dict(p) for p in positionen],
    }


def speichere_variante(pferd_id: int, name: str, beschreibung: str,
                       positionen: list, variante_id: int | None = None) -> int:
    """
    Legt eine neue Variante an oder aktualisiert eine bestehende.
    positionen: list of dicts mit Keys:
        quell_typ, futtermittel_id, supplement_id, heu_qualitaet_id, menge_kg
    Returns: variante_id
    """
    jetzt = datetime.now().isoformat()
    with get_connection() as conn:
        if variante_id:
            conn.execute(
                "UPDATE optimierungs_variante SET name=?, beschreibung=?, geaendert_am=? WHERE id=?",
                (name, beschreibung, jetzt, variante_id),
            )
            conn.execute(
                "DELETE FROM variante_position WHERE variante_id=?", (variante_id,)
            )
        else:
            cur = conn.execute(
                """INSERT INTO optimierungs_variante
                   (pferd_id, name, beschreibung, erstellt_am, geaendert_am)
                   VALUES (?,?,?,?,?)""",
                (pferd_id, name, beschreibung, jetzt, jetzt),
            )
            variante_id = cur.lastrowid

        for sort_i, pos in enumerate(positionen):
            conn.execute(
                """INSERT INTO variante_position
                   (variante_id, quell_typ, futtermittel_id, supplement_id,
                    heu_qualitaet_id, menge_kg, sort_order)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    variante_id,
                    pos.get("quell_typ"),
                    pos.get("futtermittel_id"),
                    pos.get("supplement_id"),
                    pos.get("heu_qualitaet_id"),
                    pos.get("menge_kg", 0.0),
                    sort_i,
                ),
            )
    return variante_id


def loesche_variante(variante_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM optimierungs_variante WHERE id=?", (variante_id,)
        )


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
                         positionen: list,
                         heu_mahlzeiten: int = 2,
                         heu_verlust_pct: float = 0.0) -> int:
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
                                  heu_mahlzeiten, heu_verlust_pct,
                                  erstellt_am, geaendert_am)
            VALUES (?, 'Ist-Schema', ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (pferd_id, heu_qualitaet_id, heu_menge_kg, heu_mahlzeiten, heu_verlust_pct))
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
