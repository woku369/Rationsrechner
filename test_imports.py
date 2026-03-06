"""Schnelltest aller Module."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

errors = []

def check(name, fn):
    try:
        fn()
        print(f"  OK  {name}")
    except Exception as e:
        print(f"FEHLER {name}: {e}")
        errors.append(name)

check("database import",         lambda: __import__("database"))
check("database.init_db()",      lambda: __import__("database").init_db())
check("bedarfsberechnung",       lambda: __import__("bedarfsberechnung"))
check("rationsrechner",          lambda: __import__("rationsrechner"))
check("export_module",           lambda: __import__("export_module"))
check("views/__init__",          lambda: __import__("views"))
check("views.dashboard_view",    lambda: __import__("views.dashboard_view"))
check("views.kunden_view",       lambda: __import__("views.kunden_view"))
check("views.futtermittel_view", lambda: __import__("views.futtermittel_view"))
check("views.rations_view",      lambda: __import__("views.rations_view"))

print()
if errors:
    print(f"FEHLER in: {', '.join(errors)}")
    sys.exit(1)
else:
    print("Alle Module erfolgreich geladen.")
