"""Kunden & Pferde Verwaltung."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QGroupBox, QDialogButtonBox, QSplitter, QMessageBox,
    QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import database


DIAGNOSEN_LISTE = ["EMS", "Cushing", "PSSM1", "PSSM2", "MIM",
                   "Hufrehe", "COPD"]

# Format: (Anzeigename, wählbar)
# Nicht-wählbare Einträge werden als Gruppenüberschrift (deaktiviert) dargestellt
_RASSEN_GRUPPEN = [
    ("─── Warmblut ───────────────────", False),
    ("Warmblut (allgemein)",  True),
    ("Hannoveraner",          True),
    ("Holsteiner",            True),
    ("Westfale",              True),
    ("Oldenburger",           True),
    ("Trakehner",             True),
    ("KWPN",                  True),
    ("Bayerisches Warmblut",  True),
    ("Schwedisches Warmblut", True),
    ("Selle Français",        True),
    ("Österreichisches Warmblut", True),
    ("Andalusier / PRE",      True),
    ("Lusitano",              True),
    ("Appaloosa",             True),
    ("Quarter Horse",         True),
    ("Paint Horse",           True),
    ("Morgan",                True),
    ("─── Vollblut / Araber ─────────", False),
    ("Vollblut (Thoroughbred)", True),
    ("Araber / Vollblutaraber", True),
    ("Anglo-Araber",          True),
    ("Shagya-Araber",         True),
    ("─── Friesen / Halbblut ────────", False),
    ("Friese",                True),
    ("Freiberger",            True),
    ("Rocky Mountain Horse",  True),
    ("─── Haflinger & Cobs ──────────", False),
    ("Haflinger",             True),
    ("Tinker / Irish Cob",    True),
    ("Gypsy Cob",             True),
    ("─── Kaltblut ──────────────────", False),
    ("Kaltblut (allgemein)",  True),
    ("Noriker",               True),
    ("Schwarzwälder Fuchs",   True),
    ("Süddeutsches Kaltblut", True),
    ("Belgier",               True),
    ("Shire",                 True),
    ("Clydesdale",            True),
    ("Percheron",             True),
    ("Schleswig",             True),
    ("─── Pony / Kleinpferd ─────────", False),
    ("Pony (allgemein)",      True),
    ("Deutsches Reitpony",    True),
    ("Connemara",             True),
    ("New Forest Pony",       True),
    ("Welsh Pony",            True),
    ("Fjordpferd",            True),
    ("Paso Fino",             True),
    ("Dülmener",              True),
    ("Lewitzer",              True),
    ("Exmoor Pony",           True),
    ("Isländer",              True),
    ("Shetland Pony",         True),
]

RASSEN_TYPEN = [name for name, sel in _RASSEN_GRUPPEN if sel]


def _fuelle_rassen_combo(combo):
    """Befüllt eine QComboBox mit Rassen, gruppiert durch deaktivierte Überschriften."""
    from PyQt6.QtGui import QFont
    for name, selectable in _RASSEN_GRUPPEN:
        combo.addItem(name)
        if not selectable:
            idx = combo.count() - 1
            item = combo.model().item(idx)
            item.setEnabled(False)
            f = item.font()
            f.setBold(True)
            item.setFont(f)
NUTZUNGEN    = ["Freizeit", "Leichte_Arbeit", "Mittlere_Arbeit", "Schwere_Arbeit"]
NUTZUNG_LABEL = {
    "Freizeit":        "Freizeit / Erhaltung",
    "Leichte_Arbeit":  "Leichte Arbeit",
    "Mittlere_Arbeit": "Mittlere Arbeit",
    "Schwere_Arbeit":  "Schwere Arbeit",
}
GESCHLECHTER = ["Stute", "Hengst", "Wallach"]


class PferdDialog(QDialog):
    """Dialog zum Anlegen/Bearbeiten eines Pferdes."""

    def __init__(self, kunde_id: int, pferd: dict = None, parent=None):
        super().__init__(parent)
        self.kunde_id = kunde_id
        self.pferd = pferd or {}
        self.setWindowTitle("Pferd bearbeiten" if pferd else "Neues Pferd anlegen")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit(self.pferd.get("name", ""))
        form.addRow("Name:", self.name_edit)

        self.gewicht_spin = QDoubleSpinBox()
        self.gewicht_spin.setRange(50, 1200)
        self.gewicht_spin.setSuffix(" kg")
        self.gewicht_spin.setValue(self.pferd.get("gewicht_kg", 500))
        form.addRow("Gewicht:", self.gewicht_spin)

        self.alter_spin = QDoubleSpinBox()
        self.alter_spin.setRange(0, 40)
        self.alter_spin.setSuffix(" Jahre")
        self.alter_spin.setSingleStep(0.5)
        self.alter_spin.setValue(self.pferd.get("alter_jahre", 8))
        form.addRow("Alter:", self.alter_spin)

        self.rasse_combo = QComboBox()
        self.rasse_combo.setMaxVisibleItems(25)
        _fuelle_rassen_combo(self.rasse_combo)
        gespeicherte_rasse = self.pferd.get("rasse_typ", "Warmblut (allgemein)")
        # Rückwärtskompatibilität: alte generische Namen auf neue mappen
        _alte_namen = {"Warmblut": "Warmblut (allgemein)", "Vollblut": "Vollblut (Thoroughbred)",
                       "Pony": "Pony (allgemein)", "Kaltblut": "Kaltblut (allgemein)"}
        gespeicherte_rasse = _alte_namen.get(gespeicherte_rasse, gespeicherte_rasse)
        self.rasse_combo.setCurrentText(gespeicherte_rasse)
        form.addRow("Rasse/Typ:", self.rasse_combo)

        self.nutzung_combo = QComboBox()
        for n in NUTZUNGEN:
            self.nutzung_combo.addItem(NUTZUNG_LABEL[n], n)
        nutz = self.pferd.get("nutzung", "Freizeit")
        self.nutzung_combo.setCurrentIndex(NUTZUNGEN.index(nutz))
        form.addRow("Nutzung:", self.nutzung_combo)

        self.geschlecht_combo = QComboBox()
        self.geschlecht_combo.addItems(GESCHLECHTER)
        idx_g = GESCHLECHTER.index(self.pferd.get("geschlecht", "Stute"))
        self.geschlecht_combo.setCurrentIndex(idx_g)
        form.addRow("Geschlecht:", self.geschlecht_combo)

        # Trächtigkeit
        self.traecht_spin = QSpinBox()
        self.traecht_spin.setRange(0, 11)
        self.traecht_spin.setSpecialValueText("Nein")
        self.traecht_spin.setSuffix(". Monat")
        self.traecht_spin.setValue(self.pferd.get("traechtigkeit", 0))
        form.addRow("Trächtigkeit:", self.traecht_spin)

        # Laktation
        self.lakt_spin = QSpinBox()
        self.lakt_spin.setRange(0, 6)
        self.lakt_spin.setSpecialValueText("Nein")
        self.lakt_spin.setSuffix(". Laktationsmonat")
        self.lakt_spin.setValue(self.pferd.get("laktation", 0))
        form.addRow("Laktation:", self.lakt_spin)

        layout.addLayout(form)

        # Diagnosen
        diag_group = QGroupBox("Erkrankungen / Besonderheiten")
        diag_layout = QHBoxLayout(diag_group)
        aktive_diag = (self.pferd.get("diagnosen") or "").split(",")
        aktive_diag = [d.strip() for d in aktive_diag if d.strip()]

        self.diag_checks = {}
        for d in DIAGNOSEN_LISTE:
            cb = QCheckBox(d)
            cb.setChecked(d in aktive_diag)
            diag_layout.addWidget(cb)
            self.diag_checks[d] = cb

        layout.addWidget(diag_group)

        # Notiz
        self.notiz_edit = QTextEdit()
        self.notiz_edit.setFixedHeight(60)
        self.notiz_edit.setPlainText(self.pferd.get("notiz", ""))
        self.notiz_edit.setPlaceholderText("Notizen (Fütterungsbesonderheiten, Tierarzthinweise...)")
        form2 = QFormLayout()
        form2.addRow("Notiz:", self.notiz_edit)
        layout.addLayout(form2)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def speichern(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte einen Namen eingeben.")
            return

        diagnosen = [d for d, cb in self.diag_checks.items() if cb.isChecked()]

        daten = {
            "kunde_id":      self.kunde_id,
            "name":          self.name_edit.text().strip(),
            "gewicht_kg":    self.gewicht_spin.value(),
            "alter_jahre":   self.alter_spin.value(),
            "rasse_typ":     self.rasse_combo.currentText(),
            "nutzung":       self.nutzung_combo.currentData(),
            "geschlecht":    self.geschlecht_combo.currentText(),
            "traechtigkeit": self.traecht_spin.value(),
            "laktation":     self.lakt_spin.value(),
            "diagnosen":     ", ".join(diagnosen),
            "notiz":         self.notiz_edit.toPlainText().strip(),
        }

        if self.pferd.get("id"):
            daten["id"] = self.pferd["id"]

        database.speichere_pferd(daten)
        self.accept()


class KundenView(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._lade_kunden()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # Titel
        titel = QLabel("Kunden & Pferde")
        titel.setObjectName("section_title")
        layout.addWidget(titel)

        # Splitter: Kunden links, Pferde rechts
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Linke Seite: Kunden
        kunden_widget = QWidget()
        kunden_layout = QVBoxLayout(kunden_widget)
        kunden_layout.setContentsMargins(0, 0, 0, 0)

        k_header = QHBoxLayout()
        k_titel = QLabel("Kundenliste")
        k_titel.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        k_header.addWidget(k_titel)
        k_header.addStretch()

        k_neu_btn = QPushButton("+ Neuer Kunde")
        k_neu_btn.clicked.connect(self._neuer_kunde)
        k_header.addWidget(k_neu_btn)

        kunden_layout.addLayout(k_header)

        self.kunden_tabelle = QTableWidget(0, 3)
        self.kunden_tabelle.setHorizontalHeaderLabels(["Name", "Telefon", "E-Mail"])
        self.kunden_tabelle.horizontalHeader().setStretchLastSection(True)
        self.kunden_tabelle.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.kunden_tabelle.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.kunden_tabelle.selectionModel().selectionChanged.connect(
            self._kunde_gewaehlt)
        kunden_layout.addWidget(self.kunden_tabelle)

        k_btn_layout = QHBoxLayout()
        self.k_bearbeiten_btn = QPushButton("Bearbeiten")
        self.k_bearbeiten_btn.clicked.connect(self._kunde_bearbeiten)
        self.k_loeschen_btn = QPushButton("Löschen")
        self.k_loeschen_btn.setObjectName("danger_btn")
        self.k_loeschen_btn.clicked.connect(self._kunde_loeschen)
        k_btn_layout.addStretch()
        k_btn_layout.addWidget(self.k_bearbeiten_btn)
        k_btn_layout.addWidget(self.k_loeschen_btn)
        kunden_layout.addLayout(k_btn_layout)

        splitter.addWidget(kunden_widget)

        # Rechte Seite: Pferde
        pferde_widget = QWidget()
        pferde_layout = QVBoxLayout(pferde_widget)
        pferde_layout.setContentsMargins(0, 0, 0, 0)

        p_header = QHBoxLayout()
        self.pferde_titel = QLabel("Pferde")
        self.pferde_titel.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p_header.addWidget(self.pferde_titel)
        p_header.addStretch()

        self.p_neu_btn = QPushButton("+ Neues Pferd")
        self.p_neu_btn.clicked.connect(self._neues_pferd)
        self.p_neu_btn.setEnabled(False)
        p_header.addWidget(self.p_neu_btn)

        pferde_layout.addLayout(p_header)

        self.pferde_tabelle = QTableWidget(0, 5)
        self.pferde_tabelle.setHorizontalHeaderLabels(
            ["Name", "Gewicht", "Alter", "Nutzung", "Diagnosen"])
        self.pferde_tabelle.horizontalHeader().setStretchLastSection(True)
        self.pferde_tabelle.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.pferde_tabelle.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        pferde_layout.addWidget(self.pferde_tabelle)

        p_btn_layout = QHBoxLayout()
        self.p_bearbeiten_btn = QPushButton("Bearbeiten")
        self.p_bearbeiten_btn.clicked.connect(self._pferd_bearbeiten)
        self.p_loeschen_btn = QPushButton("Löschen")
        self.p_loeschen_btn.setObjectName("danger_btn")
        self.p_loeschen_btn.clicked.connect(self._pferd_loeschen)
        p_btn_layout.addStretch()
        p_btn_layout.addWidget(self.p_bearbeiten_btn)
        p_btn_layout.addWidget(self.p_loeschen_btn)
        pferde_layout.addLayout(p_btn_layout)

        splitter.addWidget(pferde_widget)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

        self._aktueller_kunde_id = None
        self._kunden_daten = []
        self._pferde_daten = []

    def _lade_kunden(self):
        self._kunden_daten = database.alle_kunden()
        self.kunden_tabelle.setRowCount(0)
        for k in self._kunden_daten:
            row = self.kunden_tabelle.rowCount()
            self.kunden_tabelle.insertRow(row)
            self.kunden_tabelle.setItem(row, 0, QTableWidgetItem(k["name"]))
            self.kunden_tabelle.setItem(row, 1, QTableWidgetItem(k.get("telefon") or ""))
            self.kunden_tabelle.setItem(row, 2, QTableWidgetItem(k.get("email") or ""))

    def _lade_pferde(self, kunde_id: int):
        self._pferde_daten = database.pferde_von_kunde(kunde_id)
        self.pferde_tabelle.setRowCount(0)
        for p in self._pferde_daten:
            row = self.pferde_tabelle.rowCount()
            self.pferde_tabelle.insertRow(row)
            self.pferde_tabelle.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.pferde_tabelle.setItem(row, 1, QTableWidgetItem(f"{p['gewicht_kg']:.0f} kg"))
            self.pferde_tabelle.setItem(row, 2, QTableWidgetItem(f"{p['alter_jahre']:.1f} J."))
            self.pferde_tabelle.setItem(row, 3, QTableWidgetItem(
                NUTZUNG_LABEL.get(p["nutzung"], p["nutzung"])))
            self.pferde_tabelle.setItem(row, 4, QTableWidgetItem(p.get("diagnosen") or "–"))

    def _kunde_gewaehlt(self):
        rows = self.kunden_tabelle.selectedItems()
        if rows:
            row_idx = self.kunden_tabelle.currentRow()
            k = self._kunden_daten[row_idx]
            self._aktueller_kunde_id = k["id"]
            self.pferde_titel.setText(f"Pferde von: {k['name']}")
            self.p_neu_btn.setEnabled(True)
            self._lade_pferde(k["id"])

    def _neuer_kunde(self):
        dialog = _KundenDialog(parent=self)
        if dialog.exec():
            self._lade_kunden()

    def _kunde_bearbeiten(self):
        row = self.kunden_tabelle.currentRow()
        if row < 0:
            return
        k = self._kunden_daten[row]
        dialog = _KundenDialog(kunde=k, parent=self)
        if dialog.exec():
            self._lade_kunden()

    def _kunde_loeschen(self):
        row = self.kunden_tabelle.currentRow()
        if row < 0:
            return
        k = self._kunden_daten[row]
        antwort = QMessageBox.question(
            self, "Löschen bestätigen",
            f"Kunde '{k['name']}' und alle Pferde wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if antwort == QMessageBox.StandardButton.Yes:
            from database import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM kunden WHERE id=?", (k["id"],))
            self._lade_kunden()
            self.pferde_tabelle.setRowCount(0)

    def _neues_pferd(self):
        if not self._aktueller_kunde_id:
            return
        dialog = PferdDialog(self._aktueller_kunde_id, parent=self)
        if dialog.exec():
            self._lade_pferde(self._aktueller_kunde_id)

    def _pferd_bearbeiten(self):
        row = self.pferde_tabelle.currentRow()
        if row < 0:
            return
        p = self._pferde_daten[row]
        dialog = PferdDialog(self._aktueller_kunde_id, pferd=p, parent=self)
        if dialog.exec():
            self._lade_pferde(self._aktueller_kunde_id)

    def _pferd_loeschen(self):
        row = self.pferde_tabelle.currentRow()
        if row < 0:
            return
        p = self._pferde_daten[row]
        antwort = QMessageBox.question(
            self, "Löschen bestätigen",
            f"Pferd '{p['name']}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if antwort == QMessageBox.StandardButton.Yes:
            from database import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM pferde WHERE id=?", (p["id"],))
            self._lade_pferde(self._aktueller_kunde_id)


class _KundenDialog(QDialog):
    def __init__(self, kunde: dict = None, parent=None):
        super().__init__(parent)
        self.kunde = kunde or {}
        self.setWindowTitle("Kunde bearbeiten" if kunde else "Neuer Kunde")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.name_edit  = QLineEdit(self.kunde.get("name", ""))
        self.adr_edit   = QLineEdit(self.kunde.get("adresse", ""))
        self.tel_edit   = QLineEdit(self.kunde.get("telefon", ""))
        self.mail_edit  = QLineEdit(self.kunde.get("email", ""))

        layout.addRow("Name *:",    self.name_edit)
        layout.addRow("Adresse:",   self.adr_edit)
        layout.addRow("Telefon:",   self.tel_edit)
        layout.addRow("E-Mail:",    self.mail_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._speichern)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _speichern(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Fehler", "Name ist Pflichtfeld.")
            return
        daten = {
            "name":     self.name_edit.text().strip(),
            "adresse":  self.adr_edit.text().strip(),
            "telefon":  self.tel_edit.text().strip(),
            "email":    self.mail_edit.text().strip(),
        }
        if self.kunde.get("id"):
            daten["id"] = self.kunde["id"]
        database.speichere_kunden(daten)
        self.accept()
