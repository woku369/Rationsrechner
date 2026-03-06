"""Dashboard-Ansicht: Übersicht und Schnellzugriff."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import database


class StatCard(QFrame):
    """Statistik-Karte für das Dashboard."""
    def __init__(self, titel: str, farbe: str = "#4A90D9"):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 8px;
                border-left: 4px solid {farbe};
                padding: 5px;
            }}
        """)
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.wert_label = QLabel("–")
        self.wert_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.wert_label.setStyleSheet(f"color: {farbe}; border: none;")

        self.titel_label = QLabel(titel)
        self.titel_label.setStyleSheet("color: #6C757D; font-size: 12px; border: none;")

        layout.addWidget(self.wert_label)
        layout.addWidget(self.titel_label)

    def setze_wert(self, wert):
        self.wert_label.setText(str(wert))


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        # Titel
        titel = QLabel("Dashboard")
        titel.setObjectName("section_title")
        layout.addWidget(titel)

        untertitel = QLabel("Übersicht Gurktaler Pferdefutter-Rationsrechner")
        untertitel.setObjectName("info_label")
        layout.addWidget(untertitel)

        # Statistik-Karten
        karten_layout = QHBoxLayout()
        karten_layout.setSpacing(15)

        self.card_kunden     = StatCard("Kunden",           "#4A90D9")
        self.card_pferde     = StatCard("Pferde",           "#6BCB77")
        self.card_futter     = StatCard("Futtermittel",     "#FFB347")
        self.card_rationen   = StatCard("Rationen gesamt",  "#9B59B6")

        for card in [self.card_kunden, self.card_pferde,
                     self.card_futter, self.card_rationen]:
            karten_layout.addWidget(card)

        layout.addLayout(karten_layout)

        # Info-Box
        info = QFrame()
        info.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #DEE2E6;
            }
        """)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(20, 20, 20, 20)

        info_titel = QLabel("Schnellstart")
        info_titel.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        info_titel.setStyleSheet("color: #2E4057;")
        info_layout.addWidget(info_titel)

        schritte = [
            ("1", "Kunden & Pferde", "Legen Sie Ihre Kunden und deren Pferde an."),
            ("2", "Futtermittel",    "Erfassen Sie Futtermittel manuell oder per Etikett-Foto."),
            ("3", "Rationsrechner",  "Stellen Sie die Ration zusammen und vergleichen Sie mit dem Bedarf."),
            ("4", "Export",          "Exportieren Sie das Ergebnis als PDF oder Excel-Datei."),
        ]

        for nr, titel, text in schritte:
            zeile = QHBoxLayout()
            nr_label = QLabel(nr)
            nr_label.setFixedSize(28, 28)
            nr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nr_label.setStyleSheet("""
                background-color: #4A90D9;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            """)
            zeile.addWidget(nr_label)

            text_widget = QVBoxLayout()
            t_label = QLabel(titel)
            t_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            t_label.setStyleSheet("color: #2E4057;")
            d_label = QLabel(text)
            d_label.setStyleSheet("color: #6C757D; font-size: 11px;")
            text_widget.addWidget(t_label)
            text_widget.addWidget(d_label)
            zeile.addLayout(text_widget)
            zeile.addStretch()

            info_layout.addLayout(zeile)
            if nr != "4":
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("background-color: #F0F0F0; border: none;")
                line.setFixedHeight(1)
                info_layout.addWidget(line)

        layout.addWidget(info)
        layout.addStretch()

    def aktualisiere(self):
        """Aktualisiert die Statistik-Karten."""
        try:
            import database
            from database import get_connection
            with get_connection() as conn:
                kunden  = conn.execute("SELECT COUNT(*) FROM kunden").fetchone()[0]
                pferde  = conn.execute("SELECT COUNT(*) FROM pferde").fetchone()[0]
                futter  = conn.execute("SELECT COUNT(*) FROM futtermittel WHERE aktiv=1").fetchone()[0]
                rat     = conn.execute("SELECT COUNT(*) FROM rationen WHERE aktiv=1").fetchone()[0]

            self.card_kunden.setze_wert(kunden)
            self.card_pferde.setze_wert(pferde)
            self.card_futter.setze_wert(futter)
            self.card_rationen.setze_wert(rat)
        except Exception:
            pass
