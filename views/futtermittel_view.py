"""Futtermittel-Datenbank: Übersicht, Bearbeitung und OCR-Import."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDialogButtonBox,
    QGroupBox, QGridLayout, QMessageBox, QFileDialog,
    QTextEdit, QScrollArea, QSplitter, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import database

KATEGORIEN = ["Raufutter", "Kraftfutter", "Ergaenzungsfutter",
              "Mineralfutter", "Rohstoff", "Heu", "Mischfutter"]


class OCRThread(QThread):
    """Hintergrundthread für OCR-Import."""
    fertig = pyqtSignal(dict)
    fehler = pyqtSignal(str)

    def __init__(self, bild_pfad: str):
        super().__init__()
        self.bild_pfad = bild_pfad

    def run(self):
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from ocr_import import importiere_etikett
            ergebnis = importiere_etikett(self.bild_pfad)
            self.fertig.emit(ergebnis)
        except Exception as e:
            self.fehler.emit(str(e))


class FuttermittelDialog(QDialog):
    """Dialog zum Anlegen/Bearbeiten eines Futtermittels."""

    def __init__(self, futtermittel: dict = None, parent=None):
        super().__init__(parent)
        self.fm = futtermittel or {}
        self._gespeichert = False  # Guard gegen Doppel-Speichern (Signal-Mehrfachaufruf)
        self.setWindowTitle("Futtermittel bearbeiten" if futtermittel else "Neues Futtermittel")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: Allgemein
        tab1 = QWidget()
        t1 = QFormLayout(tab1)
        t1.setSpacing(8)

        self.name_edit      = QLineEdit(self.fm.get("name", ""))
        self.hersteller_edit= QLineEdit(self.fm.get("hersteller", "") or "")
        self.kat_combo      = QComboBox()
        self.kat_combo.addItems(KATEGORIEN)
        if self.fm.get("kategorie") in KATEGORIEN:
            self.kat_combo.setCurrentIndex(KATEGORIEN.index(self.fm["kategorie"]))
        self.typ_edit       = QLineEdit(self.fm.get("produkt_typ", "") or "")
        self.wasser_spin    = QDoubleSpinBox()
        self.wasser_spin.setRange(0, 95)
        self.wasser_spin.setSuffix(" %")
        self.wasser_spin.setValue(self.fm.get("wassergehalt_pct", 12.0) or 12.0)
        self.quelle_edit    = QLineEdit(self.fm.get("quelle", "") or "")

        t1.addRow("Name *:",        self.name_edit)
        t1.addRow("Hersteller:",    self.hersteller_edit)
        t1.addRow("Kategorie:",     self.kat_combo)
        t1.addRow("Typ:",           self.typ_edit)
        t1.addRow("Wassergehalt:",  self.wasser_spin)
        t1.addRow("Datenquelle:",   self.quelle_edit)
        tabs.addTab(tab1, "Allgemein")

        # Tab 2: Hauptnährstoffe
        tab2 = QWidget()
        t2 = QGridLayout(tab2)
        t2.setSpacing(8)

        def spin(min_v=0, max_v=100, suffix="", decimals=2, val=0):
            s = QDoubleSpinBox()
            s.setRange(min_v, max_v)
            s.setDecimals(decimals)
            s.setSuffix(f" {suffix}" if suffix else "")
            s.setValue(val)
            return s

        self.f = {}  # Alle Felder

        def get(key):
            v = self.fm.get(key)
            return float(v) if v is not None else 0.0

        # Hauptnährstoffe
        felder_haupt = [
            ("energie_mj_me",  "Energie (MJ ME/kg TS)",  0, 999_999, "MJ", 2, get("energie_mj_me")),
            ("rohprotein_pct", "Rohprotein (%)",          0, 999_999, "%",  2, get("rohprotein_pct")),
            ("lysin_g",        "Lysin (g/kg TS)",         0, 999_999, "g",  3, get("lysin_g")),
            ("methionin_g",    "Methionin (g/kg TS)",     0, 999_999, "g",  3, get("methionin_g")),
            ("rohfett_pct",    "Rohfett (%)",             0, 999_999, "%",  2, get("rohfett_pct")),
            ("rohfaser_pct",   "Rohfaser (%)",            0, 999_999, "%",  2, get("rohfaser_pct")),
            ("staerke_pct",    "Stärke (%)",              0, 999_999, "%",  2, get("staerke_pct")),
            ("zucker_pct",     "Zucker (%)",              0, 999_999, "%",  2, get("zucker_pct")),
        ]

        for i, (key, label, mn, mx, suf, dec, val) in enumerate(felder_haupt):
            t2.addWidget(QLabel(label + ":"), i, 0)
            w = spin(mn, mx, suf, dec, val)
            t2.addWidget(w, i, 1)
            self.f[key] = w

        tabs.addTab(tab2, "Hauptnährstoffe")

        # Tab 3: Mineralstoffe
        tab3 = QWidget()
        t3 = QGridLayout(tab3)
        t3.setSpacing(8)

        felder_min = [
            ("calcium_g",   "Calcium (g/kg TS)",    0, 999_999, "g", 3),
            ("phosphor_g",  "Phosphor (g/kg TS)",   0, 999_999, "g", 3),
            ("magnesium_g", "Magnesium (g/kg TS)",  0, 999_999, "g", 3),
            ("natrium_g",   "Natrium (g/kg TS)",    0, 999_999, "g", 3),
            ("kalium_g",    "Kalium (g/kg TS)",     0, 999_999, "g", 3),
            ("eisen_mg",    "Eisen (mg/kg TS)",     0, 999_999, "mg", 1),
            ("kupfer_mg",   "Kupfer (mg/kg TS)",    0, 999_999, "mg", 1),
            ("zink_mg",     "Zink (mg/kg TS)",      0, 999_999, "mg", 1),
            ("mangan_mg",   "Mangan (mg/kg TS)",    0, 999_999, "mg", 1),
            ("selen_mg",    "Selen (mg/kg TS)",     0, 999_999, "mg", 3),
            ("jod_mg",      "Jod (mg/kg TS)",       0, 999_999, "mg", 3),
        ]

        for i, (key, label, mn, mx, suf, dec) in enumerate(felder_min):
            row, col = divmod(i, 2)
            t3.addWidget(QLabel(label + ":"), row, col * 2)
            w = spin(mn, mx, suf, dec, get(key))
            t3.addWidget(w, row, col * 2 + 1)
            self.f[key] = w

        tabs.addTab(tab3, "Mineralstoffe & Spurenelemente")

        # Tab 4: Vitamine
        tab4 = QWidget()
        t4 = QFormLayout(tab4)
        t4.setSpacing(8)

        felder_vit = [
            ("vit_a_ie",  "Vitamin A (IE/kg TS)",   0, 999_999_999, "IE", 0),
            ("vit_d_ie",  "Vitamin D (IE/kg TS)",   0, 999_999_999, "IE", 0),
            ("vit_e_mg",  "Vitamin E (mg/kg TS)",   0, 999_999,     "mg", 1),
            ("vit_b1_mg", "Vitamin B1 (mg/kg TS)",  0, 999_999,     "mg", 2),
            ("biotin_mcg","Biotin (µg/kg TS)",      0, 999_999_999, "µg", 0),
        ]

        for key, label, mn, mx, suf, dec in felder_vit:
            w = spin(mn, mx, suf, dec, get(key))
            t4.addRow(label + ":", w)
            self.f[key] = w

        tabs.addTab(tab4, "Vitamine")

        main_layout.addWidget(tabs)

        # OCR-Import Button
        ocr_layout = QHBoxLayout()
        ocr_btn = QPushButton("📷 Nährwerte per Etikett-Foto importieren (OCR)")
        ocr_btn.setObjectName("secondary_btn")
        ocr_btn.clicked.connect(self._ocr_import)
        ocr_layout.addWidget(ocr_btn)
        ocr_layout.addStretch()
        main_layout.addLayout(ocr_layout)

        self.ocr_status = QLabel("")
        self.ocr_status.setObjectName("info_label")
        main_layout.addWidget(self.ocr_status)

        # Speichern/Abbrechen
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._speichern)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _ocr_import(self):
        pfad, _ = QFileDialog.getOpenFileName(
            self, "Etikett-Foto öffnen", "",
            "Bilder (*.jpg *.jpeg *.png *.bmp *.tiff *.webp)")
        if not pfad:
            return

        self.ocr_status.setText("⏳ OCR läuft... (kann 10–30 Sek. dauern)")
        self._ocr_thread = OCRThread(pfad)
        self._ocr_thread.fertig.connect(self._ocr_fertig)
        self._ocr_thread.fehler.connect(self._ocr_fehler)
        self._ocr_thread.start()

    def _ocr_fertig(self, daten: dict):
        erkannt = 0
        for key, wert in daten.items():
            if key == "ocr_rohtext":
                continue
            if key in self.f:
                try:
                    self.f[key].setValue(float(wert))
                    erkannt += 1
                except (ValueError, TypeError):
                    pass

        if erkannt > 0:
            self.ocr_status.setText(f"✓ {erkannt} Nährwerte erkannt. Bitte prüfen und ggf. korrigieren.")
            self.ocr_status.setStyleSheet("color: green;")
        else:
            self.ocr_status.setText("⚠ Keine Nährwerte erkannt. Bitte manuell eingeben.")
            self.ocr_status.setStyleSheet("color: orange;")

    def _ocr_fehler(self, fehler: str):
        self.ocr_status.setText(f"✗ OCR-Fehler: {fehler}")
        self.ocr_status.setStyleSheet("color: red;")

    def _speichern(self):
        if self._gespeichert:   # Guard: verhindert Doppel-INSERT bei mehrfachem Signal
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Fehler", "Name ist Pflichtfeld.")
            return

        daten = {
            "name":             self.name_edit.text().strip(),
            "hersteller":       self.hersteller_edit.text().strip() or None,
            "kategorie":        self.kat_combo.currentText(),
            "produkt_typ":      self.typ_edit.text().strip() or None,
            "wassergehalt_pct": self.wasser_spin.value(),
            "quelle":           self.quelle_edit.text().strip() or "Eigeneingabe",
        }

        for key, widget in self.f.items():
            val = widget.value()
            daten[key] = val if val > 0 else None

        # NSC berechnen
        st = (daten.get("staerke_pct") or 0)
        zu = (daten.get("zucker_pct") or 0)
        if st + zu > 0:
            daten["nsc_pct"] = st + zu

        if self.fm.get("id"):
            daten["id"] = self.fm["id"]

        self._gespeichert = True   # Guard setzen – ab hier kein zweites Speichern
        database.speichere_futtermittel(daten)
        self.accept()


# ======================================================================
# MISCHFUTTERMITTEL-DIALOGE
# ======================================================================

class KomponenteDialog(QDialog):
    """Kleiner Dialog: Futtermittel wählen + kg-Menge eingeben."""

    def __init__(self, alle_fm: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Komponente hinzufügen")
        self.setMinimumWidth(380)
        self._alle_fm = alle_fm
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.fm_combo = QComboBox()
        self.fm_combo.setMinimumWidth(300)
        for fm in self._alle_fm:
            anzeige = fm["name"]
            if fm.get("hersteller"):
                anzeige += f"  ({fm['hersteller']})"
            self.fm_combo.addItem(anzeige, fm)
        layout.addRow("Futtermittel:", self.fm_combo)

        self.menge_spin = QDoubleSpinBox()
        self.menge_spin.setRange(0.001, 9999.0)
        self.menge_spin.setDecimals(3)
        self.menge_spin.setSuffix(" kg (FM)")
        self.menge_spin.setValue(1.0)
        layout.addRow("Menge pro Charge:", self.menge_spin)

        hint = QLabel("Tipp: Gib reale Mengenverhältnisse ein,\n"
                      "z.B. 7 kg Hafer + 2 kg Lein + 1 kg Mineral.\n"
                      "Die Nährwerte werden normiert berechnet.")
        hint.setObjectName("info_label")
        layout.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_auswahl(self):
        return self.fm_combo.currentData(), self.menge_spin.value()


class MischfutterDialog(QDialog):
    """Dialog zum Anlegen/Bearbeiten einer eigenen Futtermischung."""

    def __init__(self, misch_fm: dict = None, parent=None):
        super().__init__(parent)
        self._misch_fm = misch_fm or {}
        self._gespeichert = False  # Guard gegen Doppel-Speichern
        alle = database.alle_futtermittel()
        # Keine Mischfutter als Komponente (keine Zirkelbezüge)
        self._alle_fm = [fm for fm in alle if fm.get("kategorie") != "Mischfutter"]
        # [[fm_dict, anteil_kg], ...]
        self._komponenten = []
        if misch_fm and misch_fm.get("id"):
            fm_lookup = {fm["id"]: fm for fm in alle}
            for k in database.lade_mischfutter_komponenten(misch_fm["id"]):
                fm_dict = fm_lookup.get(k["id"])
                if fm_dict:
                    self._komponenten.append([fm_dict, k["_anteil_kg"]])

        self.setWindowTitle("Mischung bearbeiten" if misch_fm else "Neue eigene Mischung")
        self.setMinimumWidth(800)
        self.setMinimumHeight(640)
        self._setup_ui()
        self._aktualisiere()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Stammdaten ---
        form = QFormLayout()
        form.setSpacing(8)
        self.name_edit = QLineEdit(self._misch_fm.get("name", ""))
        self.name_edit.setPlaceholderText("z.B. Eigenes Basisfutter")
        self.hersteller_edit = QLineEdit(self._misch_fm.get("hersteller", "") or "")
        self.hersteller_edit.setPlaceholderText("Optional: Stall / Betrieb")
        self.quelle_edit = QLineEdit(self._misch_fm.get("quelle", "Eigene Mischung") or "Eigene Mischung")
        form.addRow("Name *:", self.name_edit)
        form.addRow("Hersteller:", self.hersteller_edit)
        form.addRow("Quelle / Bezeichnung:", self.quelle_edit)
        layout.addLayout(form)

        # --- Komponenten ---
        komp_lbl = QLabel("⚗ Komponenten der Mischung")
        komp_lbl.setObjectName("section_title")
        layout.addWidget(komp_lbl)

        self.komp_tabelle = QTableWidget(0, 5)
        self.komp_tabelle.setHorizontalHeaderLabels(
            ["Futtermittel", "Hersteller", "kg (FM)", "Energie (MJ/kg TS)", "RP (%)"])
        hh = self.komp_tabelle.horizontalHeader()
        hh.setStretchLastSection(False)
        self.komp_tabelle.setColumnWidth(0, 240)
        self.komp_tabelle.setColumnWidth(1, 140)
        self.komp_tabelle.setColumnWidth(2, 80)
        self.komp_tabelle.setColumnWidth(3, 130)
        self.komp_tabelle.setColumnWidth(4, 80)
        self.komp_tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.komp_tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.komp_tabelle.setMinimumHeight(160)
        layout.addWidget(self.komp_tabelle)

        kb = QHBoxLayout()
        add_btn = QPushButton("+ Komponente hinzufügen")
        add_btn.clicked.connect(self._komponente_hinzufuegen)
        rem_btn = QPushButton("Entfernen")
        rem_btn.setObjectName("danger_btn")
        rem_btn.clicked.connect(self._komponente_entfernen)
        kb.addWidget(add_btn)
        kb.addWidget(rem_btn)
        kb.addStretch()
        layout.addLayout(kb)

        # --- Berechnete Nährwerte ---
        ergebnis_group = QGroupBox("📊 Berechnete Nährwerte der Mischung (je kg TS)")
        eg = QGridLayout(ergebnis_group)
        eg.setSpacing(6)
        self._ergebnis_labels = {}
        felder_anzeige = [
            ("wassergehalt_pct", "Wassergehalt (%)"),
            ("energie_mj_me",   "Energie (MJ ME/kg TS)"),
            ("rohprotein_pct",  "Rohprotein (%)"),
            ("rohfett_pct",     "Rohfett (%)"),
            ("rohfaser_pct",    "Rohfaser (%)"),
            ("staerke_pct",     "Stärke (%)"),
            ("zucker_pct",      "Zucker (%)"),
            ("nsc_pct",         "NSC (Stärke+Zucker %)"),
            ("calcium_g",       "Calcium (g/kg TS)"),
            ("phosphor_g",      "Phosphor (g/kg TS)"),
            ("magnesium_g",     "Magnesium (g/kg TS)"),
            ("natrium_g",       "Natrium (g/kg TS)"),
            ("kupfer_mg",       "Kupfer (mg/kg TS)"),
            ("zink_mg",         "Zink (mg/kg TS)"),
        ]
        for i, (key, label) in enumerate(felder_anzeige):
            row, col = divmod(i, 2)
            eg.addWidget(QLabel(label + ":"), row, col * 2)
            val_lbl = QLabel("–")
            val_lbl.setObjectName("info_label")
            eg.addWidget(val_lbl, row, col * 2 + 1)
            self._ergebnis_labels[key] = val_lbl
        layout.addWidget(ergebnis_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._speichern)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _aktualisiere(self):
        """Tabelle + Nährwert-Vorschau aktualisieren."""
        self.komp_tabelle.setRowCount(0)
        for fm, kg in self._komponenten:
            row = self.komp_tabelle.rowCount()
            self.komp_tabelle.insertRow(row)
            self.komp_tabelle.setItem(row, 0, QTableWidgetItem(fm["name"]))
            self.komp_tabelle.setItem(row, 1, QTableWidgetItem(fm.get("hersteller") or "–"))
            self.komp_tabelle.setItem(row, 2, QTableWidgetItem(f"{kg:.3f}"))
            e = fm.get("energie_mj_me")
            self.komp_tabelle.setItem(row, 3, QTableWidgetItem(f"{e:.2f}" if e else "–"))
            rp = fm.get("rohprotein_pct")
            self.komp_tabelle.setItem(row, 4, QTableWidgetItem(f"{rp:.1f}" if rp else "–"))

        if self._komponenten:
            erg = database.berechne_misch_naehrstoffe(self._komponenten)
            for key, lbl in self._ergebnis_labels.items():
                v = erg.get(key)
                if v is not None and v > 0:
                    lbl.setText(f"{v:.2f}")
                else:
                    lbl.setText("–")
        else:
            for lbl in self._ergebnis_labels.values():
                lbl.setText("–")

    def _komponente_hinzufuegen(self):
        dialog = KomponenteDialog(self._alle_fm, parent=self)
        if dialog.exec():
            fm, kg = dialog.get_auswahl()
            self._komponenten.append([fm, kg])
            self._aktualisiere()

    def _komponente_entfernen(self):
        row = self.komp_tabelle.currentRow()
        if 0 <= row < len(self._komponenten):
            self._komponenten.pop(row)
            self._aktualisiere()

    def _speichern(self):
        name = self.name_edit.text().strip()
        if self._gespeichert:   # Guard: verhindert Doppel-INSERT
            return
        if not name:
            QMessageBox.warning(self, "Fehler", "Name ist Pflichtfeld.")
            return
        if not self._komponenten:
            QMessageBox.warning(self, "Fehler", "Mindestens eine Komponente erforderlich.")
            return

        naehr = database.berechne_misch_naehrstoffe(self._komponenten)

        # Nährstoffe, die 0 sind → None (nicht gespeichert)
        naehr_clean = {
            k: (v if v and v > 0 else None)
            for k, v in naehr.items()
            if not k.startswith("_")
        }

        fm_daten = {
            "name":             name,
            "hersteller":       self.hersteller_edit.text().strip() or None,
            "kategorie":        "Mischfutter",
            "produkt_typ":      "Eigenmischung",
            "wassergehalt_pct": naehr.get("wassergehalt_pct") or 12.0,
            "quelle":           self.quelle_edit.text().strip() or "Eigene Mischung",
            **{k: naehr_clean.get(k) for k in [
                "energie_mj_me", "rohprotein_pct", "lysin_g", "methionin_g",
                "rohfett_pct", "rohfaser_pct", "staerke_pct", "zucker_pct", "nsc_pct",
                "calcium_g", "phosphor_g", "magnesium_g", "natrium_g", "kalium_g",
                "eisen_mg", "kupfer_mg", "zink_mg", "mangan_mg", "selen_mg",
                "jod_mg", "kobalt_mg", "vit_a_ie", "vit_d_ie", "vit_e_mg",
                "vit_b1_mg", "biotin_mcg",
            ]},
        }
        if self._misch_fm.get("id"):
            fm_daten["id"] = self._misch_fm["id"]

        self._gespeichert = True   # Guard setzen
        fm_id = database.speichere_futtermittel(fm_daten)
        database.speichere_mischfutter(fm_id, [(fm["id"], kg) for fm, kg in self._komponenten])
        self.accept()


class FuttermittelView(QWidget):
    def __init__(self):
        super().__init__()
        self._daten = []
        self._setup_ui()
        self._lade_daten()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        titel = QLabel("Futtermittel-Datenbank")
        titel.setObjectName("section_title")
        layout.addWidget(titel)

        # Filter + Aktionen
        filter_layout = QHBoxLayout()

        self.suche_edit = QLineEdit()
        self.suche_edit.setPlaceholderText("Suchen...")
        self.suche_edit.setMaximumWidth(250)
        self.suche_edit.textChanged.connect(self._filter)
        filter_layout.addWidget(self.suche_edit)

        self.kat_filter = QComboBox()
        self.kat_filter.addItem("Alle Kategorien", None)
        for k in KATEGORIEN:
            self.kat_filter.addItem(k, k)
        self.kat_filter.currentIndexChanged.connect(self._filter)
        filter_layout.addWidget(self.kat_filter)

        filter_layout.addStretch()

        misch_btn = QPushButton("⚗️ Neue Mischung")
        misch_btn.setToolTip("Eigenes Mischfutter aus mehreren Komponenten anlegen")
        misch_btn.clicked.connect(self._neue_mischung)
        filter_layout.addWidget(misch_btn)

        neu_btn = QPushButton("+ Neues Futtermittel")
        neu_btn.clicked.connect(self._neu)
        filter_layout.addWidget(neu_btn)

        layout.addLayout(filter_layout)

        # Tabelle
        self.tabelle = QTableWidget(0, 6)
        self.tabelle.setHorizontalHeaderLabels([
            "Name", "Hersteller", "Kategorie",
            "Energie (MJ/kg)", "Rohprotein (%)", "Quelle"
        ])
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabelle.doubleClicked.connect(self._bearbeiten)
        layout.addWidget(self.tabelle)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        bearbeiten_btn = QPushButton("Bearbeiten")
        bearbeiten_btn.clicked.connect(self._bearbeiten)
        loeschen_btn = QPushButton("Löschen")
        loeschen_btn.setObjectName("danger_btn")
        loeschen_btn.clicked.connect(self._loeschen)
        btn_layout.addWidget(bearbeiten_btn)
        btn_layout.addWidget(loeschen_btn)
        layout.addLayout(btn_layout)

    def _lade_daten(self):
        self._daten = database.alle_futtermittel()
        self._befuelle_tabelle(self._daten)

    def _befuelle_tabelle(self, daten):
        self.tabelle.setRowCount(0)
        for fm in daten:
            row = self.tabelle.rowCount()
            self.tabelle.insertRow(row)
            ist_misch = fm.get("kategorie") == "Mischfutter"
            name_text = ("⚗ " if ist_misch else "") + fm["name"]
            self.tabelle.setItem(row, 0, QTableWidgetItem(name_text))
            self.tabelle.setItem(row, 1, QTableWidgetItem(fm.get("hersteller") or "–"))
            self.tabelle.setItem(row, 2, QTableWidgetItem(fm.get("kategorie") or ""))

            e = fm.get("energie_mj_me")
            self.tabelle.setItem(row, 3, QTableWidgetItem(f"{e:.1f}" if e else "–"))

            rp = fm.get("rohprotein_pct")
            self.tabelle.setItem(row, 4, QTableWidgetItem(f"{rp:.1f}" if rp else "–"))

            self.tabelle.setItem(row, 5, QTableWidgetItem(fm.get("quelle") or "–"))

            # Mischfutter-Zeilen leicht einfärben
            if ist_misch:
                farbe = QColor("#e8f4e8")
                for col in range(6):
                    item = self.tabelle.item(row, col)
                    if item:
                        item.setBackground(farbe)

    def _filter(self):
        suche = self.suche_edit.text().lower()
        kat = self.kat_filter.currentData()

        gefiltert = [
            fm for fm in self._daten
            if (not suche or suche in fm["name"].lower() or
                suche in (fm.get("hersteller") or "").lower())
            and (not kat or fm.get("kategorie") == kat)
        ]
        self._befuelle_tabelle(gefiltert)
        self._gefilterte = gefiltert

    def _aktueller_row_daten(self):
        row = self.tabelle.currentRow()
        if row < 0:
            return None
        try:
            return self._gefilterte[row]
        except AttributeError:
            return self._daten[row] if row < len(self._daten) else None

    def _neu(self):
        dialog = FuttermittelDialog(parent=self)
        if dialog.exec():
            self._lade_daten()

    def _neue_mischung(self):
        dialog = MischfutterDialog(parent=self)
        if dialog.exec():
            self._lade_daten()

    def _bearbeiten(self):
        fm = self._aktueller_row_daten()
        if not fm:
            return
        if fm.get("kategorie") == "Mischfutter":
            dialog = MischfutterDialog(misch_fm=fm, parent=self)
        else:
            dialog = FuttermittelDialog(futtermittel=fm, parent=self)
        if dialog.exec():
            self._lade_daten()

    def _loeschen(self):
        fm = self._aktueller_row_daten()
        if not fm:
            return
        antwort = QMessageBox.question(
            self, "Löschen bestätigen",
            f"'{fm['name']}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if antwort == QMessageBox.StandardButton.Yes:
            from database import get_connection
            with get_connection() as conn:
                conn.execute("UPDATE futtermittel SET aktiv=0 WHERE id=?", (fm["id"],))
            self._lade_daten()
