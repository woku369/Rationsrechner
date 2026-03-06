"""
Gurktaler Pferdefutter-Rationsrechner
Hauptanwendung - PyQt6
"""

import sys
import os

# Arbeitsverzeichnis auf lokales Laufwerk setzen
# (Python 3.13 + PyQt6 haben Probleme wenn CWD ein UNC-Netzwerkpfad ist)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_local_cwd = os.environ.get("USERPROFILE") or os.environ.get("HOMEDRIVE", "C:\\")
if not os.path.isabs(_local_cwd) or _local_cwd.startswith("\\\\"):
    _local_cwd = "C:\\"
try:
    os.chdir(_local_cwd)
except OSError:
    pass

# VIRTUAL_ENV auf UNC-Pfad kann site.py zum Absturz bringen – sicherheitshalber leeren
if os.environ.get("VIRTUAL_ENV", "").startswith("\\\\"):
    os.environ["VIRTUAL_ENV"] = ""

# Skriptverzeichnis in Python-Pfad aufnehmen
sys.path.insert(0, _script_dir)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame, QSizePolicy,
    QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

import database
from views.kunden_view import KundenView
from views.futtermittel_view import FuttermittelView
from views.rations_view import RationsView
from views.dashboard_view import DashboardView
from views.supplement_view import SupplementView


# ---------------------------------------------------------------------------
# Farbschema
# ---------------------------------------------------------------------------

STYLE = """
QMainWindow {
    background-color: #F5F5F0;
}

QWidget#sidebar {
    background-color: #2E4057;
    min-width: 200px;
    max-width: 200px;
}

QPushButton#nav_btn {
    background-color: transparent;
    color: #BCC8D8;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 13px;
    border-radius: 0px;
}

QPushButton#nav_btn:hover {
    background-color: #3D5270;
    color: white;
}

QPushButton#nav_btn:checked {
    background-color: #4A90D9;
    color: white;
    font-weight: bold;
    border-left: 4px solid #88C7FF;
}

QLabel#logo {
    color: white;
    font-size: 15px;
    font-weight: bold;
    padding: 20px;
    background-color: #1E2D40;
}

QLabel#logo_sub {
    color: #88A4C0;
    font-size: 10px;
    padding: 0px 20px 15px 20px;
    background-color: #1E2D40;
}

QFrame#content_area {
    background-color: #F5F5F0;
}

QPushButton {
    background-color: #4A90D9;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #357ABD;
}

QPushButton:pressed {
    background-color: #2868A0;
}

QPushButton#danger_btn {
    background-color: #E05252;
}

QPushButton#danger_btn:hover {
    background-color: #C03A3A;
}

QPushButton#secondary_btn {
    background-color: #6C757D;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    border: 1px solid #CED4DA;
    border-radius: 4px;
    padding: 6px 10px;
    background-color: white;
    font-size: 12px;
}

QLineEdit:focus, QComboBox:focus {
    border-color: #4A90D9;
    outline: none;
}

QTableWidget {
    border: 1px solid #DEE2E6;
    border-radius: 4px;
    background-color: white;
    gridline-color: #F0F0F0;
    font-size: 12px;
}

QTableWidget::item {
    padding: 6px;
}

QTableWidget::item:selected {
    background-color: #D0E8FF;
    color: #1A1A1A;
}

QHeaderView::section {
    background-color: #2E4057;
    color: white;
    padding: 8px;
    border: none;
    font-size: 11px;
    font-weight: bold;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #DEE2E6;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    background-color: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #2E4057;
}

QScrollArea {
    border: none;
}

QLabel#section_title {
    font-size: 18px;
    font-weight: bold;
    color: #2E4057;
    padding-bottom: 5px;
}

QLabel#info_label {
    color: #6C757D;
    font-size: 11px;
}
"""


# ---------------------------------------------------------------------------
# Sidebar-Button
# ---------------------------------------------------------------------------

class NavButton(QPushButton):
    def __init__(self, text: str, icon_char: str = ""):
        super().__init__(f"  {icon_char}  {text}")
        self.setObjectName("nav_btn")
        self.setCheckable(True)
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gurktaler Pferdefutter-Rationsrechner")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        layout.addWidget(sidebar)

        # Content-Bereich
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        self.views = {
            "dashboard":    DashboardView(),
            "kunden":       KundenView(),
            "futtermittel": FuttermittelView(),
            "supplemente":  SupplementView(),
            "ration":       RationsView(),
        }

        for v in self.views.values():
            self.stack.addWidget(v)

        layout.addWidget(self.stack)

        # Standardseite
        self._show_view("dashboard")

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("🐴 Rationsrechner")
        logo.setObjectName("logo")
        logo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(logo)

        sub = QLabel("Gurktaler Pferdefutter")
        sub.setObjectName("logo_sub")
        layout.addWidget(sub)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #3D5270;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Navigations-Buttons
        self.nav_buttons = {}

        buttons = [
            ("dashboard",    "Dashboard",       "⊞"),
            ("kunden",       "Kunden & Pferde", "●"),
            ("futtermittel", "Futtermittel",    "◈"),
            ("supplemente",  "Supplemente",     "✦"),
            ("ration",       "Rationsrechner",  "⊕"),
        ]

        layout.addSpacing(10)
        for key, label, icon in buttons:
            btn = NavButton(label, icon)
            btn.clicked.connect(lambda checked, k=key: self._show_view(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        layout.addStretch()

        # Trennlinie vor Hilfs-Aktionen
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #3D5270;")
        line2.setFixedHeight(1)
        layout.addWidget(line2)

        # Erhebungsblatt-Button
        erh_btn = QPushButton("  📋  Erhebungsblatt")
        erh_btn.setObjectName("nav_btn")
        erh_btn.setFixedHeight(44)
        erh_btn.setToolTip("Druckbares Leer-Formular zur Ist-Status-Erhebung im Stall (PDF)")
        erh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        erh_btn.clicked.connect(self._erhebungsblatt_drucken)
        layout.addWidget(erh_btn)

        # Versions-Info
        version_label = QLabel("v1.0 | GfE-Standard")
        version_label.setStyleSheet("color: #5A7499; font-size: 10px; padding: 10px 20px;")
        layout.addWidget(version_label)

        return sidebar

    def _erhebungsblatt_drucken(self):
        """Speichert ein druckbares Leer-Erhebungsformular als PDF."""
        import os
        vorschlag = os.path.join(
            os.path.expanduser("~"),
            "Pferd_Erhebungsblatt.pdf"
        )
        pfad, _ = QFileDialog.getSaveFileName(
            self, "Erhebungsblatt speichern", vorschlag,
            "PDF-Datei (*.pdf)"
        )
        if not pfad:
            return
        try:
            from export_module import export_erhebungsblatt_pdf
            export_erhebungsblatt_pdf(pfad)
            QMessageBox.information(
                self, "Fertig",
                f"Erhebungsblatt gespeichert:\n{pfad}\n\n"
                "Jetzt drucken und im Stall ausfüllen.")
            # Optional: direkt öffnen
            import subprocess, sys
            if sys.platform == "win32":
                os.startfile(pfad)
        except Exception as e:
            QMessageBox.critical(self, "Fehler",
                                 f"PDF konnte nicht erstellt werden:\n{e}")

    def _show_view(self, key: str):
        if key in self.views:
            self.stack.setCurrentWidget(self.views[key])

        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

        # Views aktualisieren wenn nötig
        if key == "dashboard":
            self.views["dashboard"].aktualisiere()
        elif key == "ration":
            self.views["ration"].lade_pferde()


# ---------------------------------------------------------------------------
# Startpunkt
# ---------------------------------------------------------------------------

def main():
    # Datenbank initialisieren
    database.init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("Gurktaler Rationsrechner")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    # Schriftart
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
