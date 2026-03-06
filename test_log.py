"""Schreibt Testergebnis in test_result.txt"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

results = []

def check(name, fn):
    try:
        fn()
        results.append(f"OK    {name}")
    except Exception as e:
        results.append(f"FEHLER {name}: {e}")

check("database",            lambda: __import__("database"))
check("database.init_db",    lambda: __import__("database").init_db())
check("bedarfsberechnung",   lambda: __import__("bedarfsberechnung"))
check("rationsrechner",      lambda: __import__("rationsrechner"))
check("export_module",       lambda: __import__("export_module"))
check("views.kunden_view",   lambda: __import__("views.kunden_view"))
check("views.futtermittel",  lambda: __import__("views.futtermittel_view"))
check("views.rations_view",  lambda: __import__("views.rations_view"))
check("views.dashboard",     lambda: __import__("views.dashboard_view"))

log_path = os.path.join(os.path.dirname(__file__), "test_result.txt")
with open(log_path, "w", encoding="utf-8") as f:
    f.write("\n".join(results) + "\n")
    any_error = any(r.startswith("FEHLER") for r in results)
    f.write("\nGesamtergebnis: " + ("FEHLER" if any_error else "ALLES OK") + "\n")
