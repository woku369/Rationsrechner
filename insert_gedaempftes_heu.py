"""
Einmalig ausführen um gedämpftes Heu in die Datenbank einzutragen.
Ausführen aus dem Projektordner: python insert_gedaempftes_heu.py
"""

import database

BEZEICHNUNG = "Mäßig – 2. Schnitt, gedämpft (COPD)"

def main():
    database.init_db()

    with database.get_connection() as conn:

        # Prüfen ob Eintrag schon existiert
        existing = conn.execute(
            "SELECT id FROM heu_qualitaet WHERE bezeichnung = ?",
            (BEZEICHNUNG,)
        ).fetchone()

        if existing:
            print(f"Eintrag '{BEZEICHNUNG}' existiert bereits (ID {existing[0]}) – nichts geändert.")
            return

        conn.execute("""
            INSERT INTO heu_qualitaet (
                bezeichnung,
                energie_min,
                energie_max,
                rp_min_pct,
                rp_max_pct,
                zucker_staerke_max_pct,
                beschreibung
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            BEZEICHNUNG,
            8.0,    # energie_min  MJ ME/kg TS
            8.5,    # energie_max
            10.0,   # rp_min_pct   2. Schnitt hat mehr RP als 1. Schnitt
            13.0,   # rp_max_pct
            10.1,   # zucker_staerke_max_pct  (11% - 8% Reduktion durch Dämpfen)
            "2. Schnitt, mäßige Qualität, 30 Min. gedämpft (Dampferzeuger von unten). "
            "Staub und Schimmelsporen >99% reduziert. Mineralstoffe erhalten. "
            "Menge trocken (vor dem Dämpfen) eingeben.",
        ))

        new_id = conn.execute(
            "SELECT id FROM heu_qualitaet WHERE bezeichnung = ?",
            (BEZEICHNUNG,)
        ).fetchone()[0]

        print(f"✅ Eintrag '{BEZEICHNUNG}' angelegt (ID {new_id}).")
        print()

        # Alle Heuqualitäten zur Kontrolle ausgeben
        print("Aktuelle heu_qualitaet Tabelle:")
        print(f"  {'ID':<4} {'Bezeichnung':<45} {'E-min':>6} {'E-max':>6} {'NSC':>6}")
        print("  " + "-" * 72)
        for row in conn.execute("SELECT id, bezeichnung, energie_min, energie_max, zucker_staerke_max_pct FROM heu_qualitaet ORDER BY id"):
            print(f"  {row[0]:<4} {row[1]:<45} {row[2]:>6.1f} {row[3]:>6.1f} {row[4]:>6.1f}")


if __name__ == "__main__":
    main()
