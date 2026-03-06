"""Supplement-Katalog: Übersicht und Verwaltung handelsüblicher Einzelpräparate."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDialogButtonBox,
    QCheckBox, QMessageBox, QTextEdit, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import database

# ---------------------------------------------------------------------------
# Stammlisten
# ---------------------------------------------------------------------------

TYPEN = [
    "Spurenelement",
    "Vitamin",
    "Aminosäure",
    "Makromineral",
    "Fettsäure",
    "Sonstiges",
]

EINHEITEN = ["mg", "g", "IE", "mcg"]

# Bekannte Nährstoff-Felder aus der Bedarfsberechnung
NAEHR_FELDER = [
    # Spurenelemente
    ("selen_mg",     "Selen (mg)"),
    ("zink_mg",      "Zink (mg)"),
    ("kupfer_mg",    "Kupfer (mg)"),
    ("mangan_mg",    "Mangan (mg)"),
    ("jod_mg",       "Jod (mg)"),
    ("kobalt_mg",    "Kobalt (mg)"),
    ("eisen_mg",     "Eisen (mg)"),
    # Vitamine
    ("vit_e_mg",     "Vitamin E (mg)"),
    ("vit_a_ie",     "Vitamin A (IE)"),
    ("vit_d_ie",     "Vitamin D (IE)"),
    ("vit_b1_mg",    "Vitamin B1 (mg)"),
    ("biotin_mcg",   "Biotin (mcg)"),
    # Aminosäuren
    ("lysin_g",      "Lysin (g)"),
    ("methionin_g",  "Methionin (g)"),
    ("threonin_g",   "Threonin (g)"),
    ("tryptophan_g", "Tryptophan (g)"),
    # Makrominerale
    ("magnesium_g",  "Magnesium (g)"),
    ("calcium_g",    "Calcium (g)"),
    ("phosphor_g",   "Phosphor (g)"),
    ("natrium_g",    "Natrium (g)"),
    # Fettsäuren
    ("rohfett_pct",  "Rohfett (%)"),
]

_FELD_ZU_ANZEIGE = {k: v for k, v in NAEHR_FELDER}


# ---------------------------------------------------------------------------
# Dialog: Supplement anlegen / bearbeiten
# ---------------------------------------------------------------------------

class SupplementDialog(QDialog):
    """Formular zum Anlegen oder Bearbeiten eines Supplements."""

    def __init__(self, supplement: dict = None, parent=None):
        super().__init__(parent)
        self.sup = supplement or {}
        self.setWindowTitle("Supplement bearbeiten" if supplement else "Neues Supplement")
        self.setMinimumWidth(560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # ── Grunddaten ──
        grp_basis = QFrame()
        grp_basis.setFrameShape(QFrame.Shape.StyledPanel)
        grp_basis.setStyleSheet("QFrame { border:1px solid #DEE2E6; border-radius:6px; padding:4px; }")
        form = QFormLayout(grp_basis)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self.name_edit = QLineEdit(self.sup.get("name", ""))
        self.name_edit.setPlaceholderText("z. B. Selenomethionin (99%), Zinkcitrat …")
        form.addRow("Produktname *:", self.name_edit)

        self.typ_combo = QComboBox()
        self.typ_combo.addItems(TYPEN)
        if self.sup.get("typ") in TYPEN:
            self.typ_combo.setCurrentIndex(TYPEN.index(self.sup["typ"]))
        form.addRow("Typ:", self.typ_combo)

        # Nährstoff-Feld: Combo + freies Textfeld nebeneinander
        feld_row = QHBoxLayout()
        self.naehr_combo = QComboBox()
        self.naehr_combo.setEditable(True)
        self.naehr_combo.addItem("– bitte wählen –", "")
        for key, anzeige in NAEHR_FELDER:
            self.naehr_combo.addItem(anzeige, key)
        # Aktuellen Wert setzen
        cur_feld = self.sup.get("naehr_feld", "")
        idx = next(
            (i for i in range(self.naehr_combo.count())
             if self.naehr_combo.itemData(i) == cur_feld),
            -1,
        )
        if idx >= 0:
            self.naehr_combo.setCurrentIndex(idx)
        elif cur_feld:
            # Unbekanntes Feld → als Text setzen
            self.naehr_combo.setCurrentText(cur_feld)
        feld_row.addWidget(self.naehr_combo)
        form.addRow("Nährstoff-Feld *:", feld_row)

        self.einheit_combo = QComboBox()
        self.einheit_combo.addItems(EINHEITEN)
        cur_einheit = self.sup.get("einheit", "mg")
        if cur_einheit in EINHEITEN:
            self.einheit_combo.setCurrentIndex(EINHEITEN.index(cur_einheit))
        form.addRow("Wirkstoff-Einheit:", self.einheit_combo)

        layout.addWidget(grp_basis)

        # ── Dosierung ──
        grp_dos = QFrame()
        grp_dos.setFrameShape(QFrame.Shape.StyledPanel)
        grp_dos.setStyleSheet("QFrame { border:1px solid #DEE2E6; border-radius:6px; padding:4px; }")
        dos_form = QFormLayout(grp_dos)
        dos_form.setSpacing(8)
        dos_form.setContentsMargins(12, 12, 12, 12)

        dos_titel = QLabel("Dosierung")
        dos_titel.setStyleSheet("font-weight: bold; color: #2E4057; font-size: 12px;")
        dos_form.addRow(dos_titel)

        self.konz_spin = QDoubleSpinBox()
        self.konz_spin.setRange(0, 10_000_000)
        self.konz_spin.setDecimals(2)
        self.konz_spin.setGroupSeparatorShown(True)
        self.konz_spin.setToolTip(
            "Wie viel Wirkstoff (in Wirkstoff-Einheit) steckt in 1 kg dieses Produkts?\n"
            "Beispiel: NaSelenit 97% → 97 g Se × 1000 mg = 970.000 mg/kg."
        )
        self.konz_spin.setValue(float(self.sup.get("konzentration_je_kg") or 0))
        dos_form.addRow("Konzentration je kg Produkt *:", self.konz_spin)

        self.maxdos_spin = QDoubleSpinBox()
        self.maxdos_spin.setRange(0, 100_000)
        self.maxdos_spin.setDecimals(3)
        self.maxdos_spin.setSpecialValueText("–")
        self.maxdos_spin.setToolTip(
            "Empfohlene maximale Tagesdosis in der Wirkstoff-Einheit.\n"
            "0 = kein Limit angegeben."
        )
        self.maxdos_spin.setValue(float(self.sup.get("max_tagesdosis_einheit") or 0))
        dos_form.addRow("Max. Tagesdosis (Wirkstoff):", self.maxdos_spin)

        layout.addWidget(grp_dos)

        # ── Metadaten ──
        grp_meta = QFrame()
        grp_meta.setFrameShape(QFrame.Shape.StyledPanel)
        grp_meta.setStyleSheet("QFrame { border:1px solid #DEE2E6; border-radius:6px; padding:4px; }")
        meta_form = QFormLayout(grp_meta)
        meta_form.setSpacing(8)
        meta_form.setContentsMargins(12, 12, 12, 12)

        self.bevorzugt_check = QCheckBox("Empfohlene / bevorzugte Form (wird im Assistenten zuerst vorgeschlagen)")
        self.bevorzugt_check.setChecked(bool(self.sup.get("bevorzugt", 0)))
        meta_form.addRow(self.bevorzugt_check)

        self.quelle_edit = QLineEdit(self.sup.get("quelle") or "Eigene Eingabe")
        meta_form.addRow("Quelle / Literatur:", self.quelle_edit)

        self.hinweis_edit = QTextEdit()
        self.hinweis_edit.setMaximumHeight(80)
        self.hinweis_edit.setPlaceholderText(
            "Hinweise zur Bioverfügbarkeit, Verträglichkeit, Lagerung …"
        )
        self.hinweis_edit.setPlainText(self.sup.get("hinweis") or "")
        meta_form.addRow("Hinweis:", self.hinweis_edit)

        layout.addWidget(grp_meta)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------

    def _naehr_feld_wert(self) -> str:
        """Gibt den Feldnamen zurück (itemData oder freier Text)."""
        idx = self.naehr_combo.currentIndex()
        data = self.naehr_combo.itemData(idx)
        if data:
            return data
        # Freitext (editable ComboBox)
        return self.naehr_combo.currentText().strip()

    def _speichern(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Produktnamen eingeben.")
            return
        naehr_feld = self._naehr_feld_wert()
        if not naehr_feld or naehr_feld == "– bitte wählen –":
            QMessageBox.warning(self, "Pflichtfeld", "Bitte ein Nährstoff-Feld auswählen.")
            return
        konz = self.konz_spin.value()
        if konz <= 0:
            QMessageBox.warning(self, "Ungültig", "Konzentration muss größer als 0 sein.")
            return

        daten = {
            "name":                   name,
            "typ":                    self.typ_combo.currentText(),
            "naehr_feld":             naehr_feld,
            "einheit":                self.einheit_combo.currentText(),
            "konzentration_je_kg":    konz,
            "max_tagesdosis_einheit": self.maxdos_spin.value() or None,
            "bevorzugt":              1 if self.bevorzugt_check.isChecked() else 0,
            "quelle":                 self.quelle_edit.text().strip() or "Eigene Eingabe",
            "hinweis":                self.hinweis_edit.toPlainText().strip() or None,
        }
        if self.sup.get("id"):
            daten["id"] = self.sup["id"]

        database.speichere_supplement(daten)
        self.accept()


# ---------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------

class SupplementView(QWidget):
    """Tabellen-Ansicht für den gesamten Supplement-Katalog mit CRUD."""

    def __init__(self):
        super().__init__()
        self._daten: list[dict] = []
        self._gefilterte: list[dict] = []
        self._setup_ui()
        self._lade_daten()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # Titel
        titel = QLabel("Supplement-Katalog")
        titel.setObjectName("section_title")
        layout.addWidget(titel)

        info = QLabel(
            "Handelsübliche Einzelpräparate — werden im Optimierungsassistenten als Ergänzungsvorschläge genutzt."
        )
        info.setStyleSheet("color: #6C757D; font-size: 11px;")
        layout.addWidget(info)

        # Filter-Zeile
        filter_row = QHBoxLayout()

        self.suche_edit = QLineEdit()
        self.suche_edit.setPlaceholderText("Name suchen …")
        self.suche_edit.setMaximumWidth(240)
        self.suche_edit.textChanged.connect(self._filter)
        filter_row.addWidget(self.suche_edit)

        self.typ_filter = QComboBox()
        self.typ_filter.addItem("Alle Typen", None)
        for t in TYPEN:
            self.typ_filter.addItem(t, t)
        self.typ_filter.currentIndexChanged.connect(self._filter)
        filter_row.addWidget(self.typ_filter)

        self.bev_filter = QComboBox()
        self.bev_filter.addItem("Alle Formen", None)
        self.bev_filter.addItem("⭐ Nur bevorzugte", 1)
        self.bev_filter.addItem("Nur Alternativen", 0)
        self.bev_filter.currentIndexChanged.connect(self._filter)
        filter_row.addWidget(self.bev_filter)

        filter_row.addStretch()

        neu_btn = QPushButton("+ Neues Supplement")
        neu_btn.clicked.connect(self._neu)
        filter_row.addWidget(neu_btn)

        layout.addLayout(filter_row)

        # Tabelle
        self.tabelle = QTableWidget(0, 8)
        self.tabelle.setHorizontalHeaderLabels([
            "Name", "Typ", "Nährstoff", "Einheit",
            "Konz. je kg", "Max-Tagesdosis", "⭐", "Hinweis",
        ])
        hh = self.tabelle.horizontalHeader()
        hh.setStretchLastSection(True)
        self.tabelle.setColumnWidth(0, 230)
        self.tabelle.setColumnWidth(1, 100)
        self.tabelle.setColumnWidth(2, 130)
        self.tabelle.setColumnWidth(3, 65)
        self.tabelle.setColumnWidth(4, 110)
        self.tabelle.setColumnWidth(5, 120)
        self.tabelle.setColumnWidth(6, 28)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabelle.doubleClicked.connect(self._bearbeiten)
        layout.addWidget(self.tabelle)

        # Aktions-Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        bearbeiten_btn = QPushButton("Bearbeiten")
        bearbeiten_btn.clicked.connect(self._bearbeiten)
        loeschen_btn = QPushButton("Löschen")
        loeschen_btn.setObjectName("danger_btn")
        loeschen_btn.clicked.connect(self._loeschen)
        btn_row.addWidget(bearbeiten_btn)
        btn_row.addWidget(loeschen_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Datenzugriff
    # ------------------------------------------------------------------

    def _lade_daten(self):
        self._daten = database.alle_supplemente()
        self._filter()

    def _befuelle_tabelle(self, daten: list):
        self.tabelle.setRowCount(0)
        for sup in daten:
            row = self.tabelle.rowCount()
            self.tabelle.insertRow(row)

            bevorzugt = bool(sup.get("bevorzugt"))

            name_item = QTableWidgetItem(sup["name"])
            self.tabelle.setItem(row, 0, name_item)
            self.tabelle.setItem(row, 1, QTableWidgetItem(sup.get("typ") or ""))

            # Nährstoff leserlich
            feld = sup.get("naehr_feld", "")
            anzeige = _FELD_ZU_ANZEIGE.get(feld, feld)
            self.tabelle.setItem(row, 2, QTableWidgetItem(anzeige))
            self.tabelle.setItem(row, 3, QTableWidgetItem(sup.get("einheit") or ""))

            konz = sup.get("konzentration_je_kg")
            if konz is not None:
                konz_txt = f"{konz:,.0f}" if konz >= 1000 else f"{konz:.3f}"
                self.tabelle.setItem(row, 4, QTableWidgetItem(konz_txt))
            else:
                self.tabelle.setItem(row, 4, QTableWidgetItem("–"))

            maxd = sup.get("max_tagesdosis_einheit")
            maxd_txt = f"{maxd:.2f}" if maxd else "–"
            self.tabelle.setItem(row, 5, QTableWidgetItem(maxd_txt))

            stern = QTableWidgetItem("⭐" if bevorzugt else "")
            stern.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabelle.setItem(row, 6, stern)

            hinweis = (sup.get("hinweis") or "")
            if len(hinweis) > 80:
                hinweis = hinweis[:77] + "…"
            self.tabelle.setItem(row, 7, QTableWidgetItem(hinweis))

            # Bevorzugte Zeilen leicht grün hinterlegen
            if bevorzugt:
                farbe = QColor("#EAF5EA")
                for col in range(8):
                    item = self.tabelle.item(row, col)
                    if item:
                        item.setBackground(farbe)

    def _filter(self):
        suche = self.suche_edit.text().lower().strip()
        typ = self.typ_filter.currentData()
        bev = self.bev_filter.currentData()

        gefiltert = [
            s for s in self._daten
            if (not suche or suche in s["name"].lower() or
                suche in (s.get("hinweis") or "").lower())
            and (typ is None or s.get("typ") == typ)
            and (bev is None or int(s.get("bevorzugt") or 0) == bev)
        ]
        self._gefilterte = gefiltert
        self._befuelle_tabelle(gefiltert)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _aktuelles_supplement(self) -> dict | None:
        row = self.tabelle.currentRow()
        if row < 0:
            return None
        try:
            return self._gefilterte[row]
        except IndexError:
            return None

    def _neu(self):
        dlg = SupplementDialog(parent=self)
        if dlg.exec():
            self._lade_daten()

    def _bearbeiten(self):
        sup = self._aktuelles_supplement()
        if not sup:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Supplement auswählen.")
            return
        dlg = SupplementDialog(supplement=sup, parent=self)
        if dlg.exec():
            self._lade_daten()

    def _loeschen(self):
        sup = self._aktuelles_supplement()
        if not sup:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Supplement auswählen.")
            return
        antwort = QMessageBox.question(
            self, "Löschen bestätigen",
            f"„{sup['name']}\" wirklich aus dem Katalog entfernen?\n"
            "(Das Supplement wird deaktiviert, nicht dauerhaft gelöscht.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if antwort == QMessageBox.StandardButton.Yes:
            database.loesche_supplement(sup["id"])
            self._lade_daten()
