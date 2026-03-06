"""Rationsrechner - Hauptansicht mit Bedarfs- und Istwertsvergleich."""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QDoubleSpinBox,
    QGroupBox, QSplitter, QScrollArea, QFrame, QHeaderView,
    QFileDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QBrush
import database
from bedarfsberechnung import PferdeParameter, berechne_bedarf
from rationsrechner import (
    berechne_ration, berechne_differenz,
    position_aus_db_row, heu_als_position
)
from views.optimierungs_view import OptimierungsDialog


# ---------------------------------------------------------------------------
# Farben für die Differenzanzeige
# ---------------------------------------------------------------------------

FARBE_OK      = QColor("#D4EDDA")   # Grün: Bedarf gedeckt
FARBE_MANGEL  = QColor("#F8D7DA")   # Rot: Unterversorgung
FARBE_UEBER   = QColor("#FFF3CD")   # Gelb: deutliche Überversorgung
FARBE_LIMIT   = QColor("#FF6B6B")   # Dunkelrot: Limit überschritten
FARBE_HEADER  = QColor("#2E4057")


class RationsView(QWidget):
    def __init__(self):
        super().__init__()
        self._pferde = []
        self._futtermittel = []
        self._heu_qualitaeten = []
        self._rations_positionen = []   # list of (db_row, menge_kg)
        self._aktuelles_pferd = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(8)

        # ── Kompakte Titelzeile: Titel + Pferd + Bedarf-Info + Export ──
        top_lo = QHBoxLayout()
        top_lo.setSpacing(10)

        titel = QLabel("Rationsrechner")
        titel.setObjectName("section_title")
        top_lo.addWidget(titel)

        top_lo.addWidget(QLabel("Pferd:"))
        self.pferd_combo = QComboBox()
        self.pferd_combo.setMinimumWidth(260)
        self.pferd_combo.currentIndexChanged.connect(self._pferd_gewaehlt)
        top_lo.addWidget(self.pferd_combo)

        self.bedarf_info = QLabel("")
        self.bedarf_info.setObjectName("info_label")
        top_lo.addWidget(self.bedarf_info, stretch=1)

        pdf_btn = QPushButton("📄 PDF")
        pdf_btn.setFixedWidth(90)
        pdf_btn.clicked.connect(lambda: self._exportieren("pdf"))
        xlsx_btn = QPushButton("📊 Excel")
        xlsx_btn.setFixedWidth(90)
        xlsx_btn.clicked.connect(lambda: self._exportieren("xlsx"))
        opt_btn = QPushButton("🔍 Optimierungsassistent")
        opt_btn.setFixedWidth(190)
        opt_btn.setStyleSheet(
            "background:#2E4057; color:white; border-radius:4px; padding:3px;"
        )
        opt_btn.clicked.connect(self._oeffne_optimierungsassistent)
        top_lo.addWidget(pdf_btn)
        top_lo.addWidget(xlsx_btn)
        top_lo.addWidget(opt_btn)
        layout.addLayout(top_lo)

        # ── Haupt-Splitter ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        linke_seite = self._baue_rations_panel()
        splitter.addWidget(linke_seite)

        rechte_seite = self._baue_vergleich_panel()
        splitter.addWidget(rechte_seite)

        splitter.setSizes([480, 720])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    def _baue_rations_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(10)

        # Heu-Gruppe
        heu_group = QGroupBox("Heu")
        heu_lo = QHBoxLayout(heu_group)

        self.heu_combo = QComboBox()
        self.heu_combo.setMinimumWidth(160)
        self.heu_combo.currentIndexChanged.connect(self._berechne)
        heu_lo.addWidget(QLabel("Qualität:"))
        heu_lo.addWidget(self.heu_combo)

        heu_lo.addWidget(QLabel("Menge:"))
        self.heu_menge = QDoubleSpinBox()
        self.heu_menge.setRange(0, 50)
        self.heu_menge.setSuffix(" kg/Tag")
        self.heu_menge.setSingleStep(0.5)
        self.heu_menge.setValue(8.0)
        self.heu_menge.valueChanged.connect(self._berechne)
        heu_lo.addWidget(self.heu_menge)
        layout.addWidget(heu_group)

        # Kraftfutter/Ergänzung hinzufügen
        add_group = QGroupBox("Futtermittel hinzufügen")
        add_lo = QHBoxLayout(add_group)

        self.fm_combo = QComboBox()
        self.fm_combo.setMinimumWidth(220)
        add_lo.addWidget(self.fm_combo)

        add_lo.addWidget(QLabel("Menge:"))
        self.fm_menge = QDoubleSpinBox()
        self.fm_menge.setRange(0.01, 100)
        self.fm_menge.setSuffix(" kg/Tag")
        self.fm_menge.setSingleStep(0.1)
        self.fm_menge.setValue(1.0)
        add_lo.addWidget(self.fm_menge)

        hinzu_btn = QPushButton("Hinzufügen")
        hinzu_btn.clicked.connect(self._position_hinzufuegen)
        add_lo.addWidget(hinzu_btn)
        layout.addWidget(add_group)

        # Rations-Tabelle
        r_label = QLabel("Aktuelle Ration:")
        r_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(r_label)

        self.rations_tabelle = QTableWidget(0, 4)
        self.rations_tabelle.setHorizontalHeaderLabels(
            ["Futtermittel", "Menge FM", "TS (kg)", "Menge ändern"])
        self.rations_tabelle.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.rations_tabelle.setColumnWidth(1, 90)
        self.rations_tabelle.setColumnWidth(2, 80)
        self.rations_tabelle.setColumnWidth(3, 130)
        self.rations_tabelle.verticalHeader().setDefaultSectionSize(36)
        self.rations_tabelle.setMinimumHeight(100)
        self.rations_tabelle.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.rations_tabelle, stretch=1)

        akt_btn_lo = QHBoxLayout()
        akt_btn_lo.addStretch()
        entf_btn = QPushButton("Entfernen")
        entf_btn.setObjectName("danger_btn")
        entf_btn.clicked.connect(self._position_entfernen)
        akt_btn_lo.addWidget(entf_btn)
        layout.addLayout(akt_btn_lo)

        # ---- Ist-Schema-Leiste ----------------------------------------
        schema_lo = QHBoxLayout()
        self.schema_info_label = QLabel("Kein Ist-Schema gespeichert")
        self.schema_info_label.setObjectName("info_label")
        schema_lo.addWidget(self.schema_info_label)
        schema_lo.addStretch()

        leeren_btn = QPushButton("\u21ba Leeren")
        leeren_btn.setToolTip("Ration leeren (gespeichertes Schema bleibt erhalten)")
        leeren_btn.clicked.connect(self._ration_leeren)
        schema_lo.addWidget(leeren_btn)

        speichern_btn = QPushButton("\U0001f4be Ist-Schema speichern")
        speichern_btn.setToolTip(
            "Speichert die aktuelle Ration als Ist-Schema f\u00fcr dieses Pferd.\n"
            "Wird beim n\u00e4chsten \u00d6ffnen automatisch geladen.")
        speichern_btn.clicked.connect(self._schema_speichern)
        schema_lo.addWidget(speichern_btn)
        layout.addLayout(schema_lo)

        # Summen
        self.summen_label = QLabel("")
        self.summen_label.setObjectName("info_label")
        self.summen_label.setWordWrap(True)
        layout.addWidget(self.summen_label)

        return widget

    def _baue_vergleich_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(5)

        v_label = QLabel("Nährstoffvergleich: Bedarf vs. Ist")
        v_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(v_label)

        self.vergleich_tabelle = QTableWidget(0, 6)
        self.vergleich_tabelle.setHorizontalHeaderLabels(
            ["Parameter", "Einheit", "Bedarf", "Ist", "Differenz", "Diff %"])
        self.vergleich_tabelle.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for col in [1, 2, 3, 4]:
            self.vergleich_tabelle.setColumnWidth(col, 90)
        self.vergleich_tabelle.setColumnWidth(5, 75)
        self.vergleich_tabelle.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.vergleich_tabelle.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.vergleich_tabelle, stretch=1)

        # Warnungen
        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #C0392B; font-weight: bold; background: #FDECEA; "
            "padding: 8px; border-radius: 4px;")
        self.warn_label.setVisible(False)
        layout.addWidget(self.warn_label)

        return widget

    # ----------------------------------------------------------------
    # Datenladen
    # ----------------------------------------------------------------

    def lade_pferde(self):
        """Muss aufgerufen werden wenn Tab aktiviert wird."""
        with database.get_connection() as conn:
            rows = conn.execute("""
                SELECT p.*, k.name as kunden_name
                FROM pferde p
                JOIN kunden k ON p.kunde_id = k.id
                ORDER BY k.name, p.name
            """).fetchall()

        self._pferde = [dict(r) for r in rows]
        self.pferd_combo.blockSignals(True)
        self.pferd_combo.clear()
        self.pferd_combo.addItem("– Pferd auswählen –", None)
        for p in self._pferde:
            self.pferd_combo.addItem(
                f"{p['name']} ({p['kunden_name']}, {p['gewicht_kg']:.0f} kg)",
                p["id"])
        self.pferd_combo.blockSignals(False)

        # Futtermittel laden
        self._futtermittel = database.alle_futtermittel()
        self.fm_combo.clear()
        for fm in self._futtermittel:
            self.fm_combo.addItem(
                f"{fm['name']}" + (f" ({fm.get('hersteller','')})" if fm.get("hersteller") else ""),
                fm)

        # Heu laden
        self._heu_qualitaeten = database.heu_qualitaeten()
        self.heu_combo.clear()
        for h in self._heu_qualitaeten:
            self.heu_combo.addItem(h["bezeichnung"], h)

    def _pferd_gewaehlt(self):
        idx = self.pferd_combo.currentIndex()
        if idx <= 0:
            self._aktuelles_pferd = None
            return

        pid = self.pferd_combo.currentData()
        self._aktuelles_pferd = next((p for p in self._pferde if p["id"] == pid), None)

        if self._aktuelles_pferd:
            p = self._aktuelles_pferd
            diag = [d.strip() for d in (p.get("diagnosen") or "").split(",") if d.strip()]
            info = (f"GfE-Bedarf berechnet | {p['rasse_typ']} | "
                    f"{', '.join(diag) if diag else 'Keine Diagnosen'}")
            self.bedarf_info.setText(info)
            self._lade_schema_fuer_pferd(pid)
            self._berechne()

    # ----------------------------------------------------------------
    # Ist-Schema: speichern / leeren / laden
    # ----------------------------------------------------------------

    def _schema_speichern(self):
        """Speichert die aktuelle Ration dauerhaft als Ist-Schema."""
        if not self._aktuelles_pferd:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Pferd ausw\u00e4hlen.")
            return
        heu_q    = self.heu_combo.currentData()
        heu_id   = heu_q["id"] if heu_q else None
        heu_menge = self.heu_menge.value()
        positionen = [(fm["id"], menge) for fm, menge in self._rations_positionen]
        database.speichere_ist_schema(
            self._aktuelles_pferd["id"], heu_id, heu_menge, positionen)
        jetzt = datetime.now().strftime("%d.%m.%Y %H:%M")
        self.schema_info_label.setText(f"\u2713 Ist-Schema gespeichert: {jetzt}")
        QMessageBox.information(
            self, "Gespeichert",
            f"Ist-Schema f\u00fcr \u201e{self._aktuelles_pferd['name']}\u201c gespeichert.\n"
            "Es wird beim n\u00e4chsten \u00d6ffnen automatisch geladen.")

    def _ration_leeren(self):
        """Leert die Ration in der Ansicht; gespeichertes Schema bleibt in der DB."""
        self._rations_positionen.clear()
        self._aktualisiere_rations_tabelle()
        self.heu_menge.setValue(8.0)
        self._berechne()

    def _lade_schema_fuer_pferd(self, pferd_id: int):
        """L\u00e4dt das gespeicherte Ist-Schema und bef\u00fcllt Heu + Positionen."""
        schema = database.lade_ist_schema(pferd_id)
        if not schema:
            self.schema_info_label.setText("Kein Ist-Schema gespeichert")
            self._rations_positionen.clear()
            self._aktualisiere_rations_tabelle()
            return

        ration = schema["ration"]

        # Heu-Menge
        heu_menge = ration.get("heu_menge_kg") or 0.0
        self.heu_menge.blockSignals(True)
        self.heu_menge.setValue(heu_menge)
        self.heu_menge.blockSignals(False)

        # Heu-Qualit\u00e4t
        if schema["heu"]:
            idx = self.heu_combo.findText(schema["heu"]["bezeichnung"])
            if idx >= 0:
                self.heu_combo.blockSignals(True)
                self.heu_combo.setCurrentIndex(idx)
                self.heu_combo.blockSignals(False)

        # Futtermittel-Positionen
        self._rations_positionen.clear()
        fm_lookup = {fm["id"]: fm for fm in self._futtermittel}
        for pos in schema["positionen"]:
            fm_data = fm_lookup.get(pos["id"])
            if fm_data:
                self._rations_positionen.append((fm_data, pos["_menge_kg"]))
        self._aktualisiere_rations_tabelle()

        # Info-Label: Datum leserlich formatieren
        datum_roh = ration.get("geaendert_am", "")[:16].replace("T", " ")
        try:
            dt    = datetime.strptime(datum_roh, "%Y-%m-%d %H:%M")
            datum = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            datum = datum_roh
        self.schema_info_label.setText(f"\u2713 Ist-Schema vom {datum}")

    # ----------------------------------------------------------------
    # Positions-Management
    # ----------------------------------------------------------------

    def _position_hinzufuegen(self):
        fm_daten = self.fm_combo.currentData()
        if not fm_daten:
            return
        menge = self.fm_menge.value()
        self._rations_positionen.append((fm_daten, menge))
        self._aktualisiere_rations_tabelle()
        self._berechne()

    def _position_entfernen(self):
        row = self.rations_tabelle.currentRow()
        if 0 <= row < len(self._rations_positionen):
            self._rations_positionen.pop(row)
            self._aktualisiere_rations_tabelle()
            self._berechne()

    def _aktualisiere_rations_tabelle(self):
        self.rations_tabelle.setRowCount(0)
        for fm_daten, menge_kg in self._rations_positionen:
            row = self.rations_tabelle.rowCount()
            self.rations_tabelle.insertRow(row)
            self.rations_tabelle.setRowHeight(row, 36)
            self.rations_tabelle.setItem(row, 0, QTableWidgetItem(fm_daten["name"]))
            self.rations_tabelle.setItem(row, 1, QTableWidgetItem(f"{menge_kg:.2f} kg"))
            tm = menge_kg * (1 - (fm_daten.get("wassergehalt_pct") or 12) / 100)
            self.rations_tabelle.setItem(row, 2, QTableWidgetItem(f"{tm:.2f} kg"))
            # SpinBox zum direkten Ändern der Menge
            edit_spin = QDoubleSpinBox()
            edit_spin.setRange(0.01, 100)
            edit_spin.setValue(menge_kg)
            edit_spin.setSuffix(" kg")
            edit_spin.setMinimumHeight(28)
            idx = row
            edit_spin.valueChanged.connect(
                lambda v, i=idx: self._menge_aendern(i, v))
            self.rations_tabelle.setCellWidget(row, 3, edit_spin)

    def _menge_aendern(self, idx: int, wert: float):
        if 0 <= idx < len(self._rations_positionen):
            fm, _ = self._rations_positionen[idx]
            self._rations_positionen[idx] = (fm, wert)
            tm = wert * (1 - (fm.get("wassergehalt_pct") or 12) / 100)
            self.rations_tabelle.setItem(idx, 1, QTableWidgetItem(f"{wert:.2f} kg"))
            self.rations_tabelle.setItem(idx, 2, QTableWidgetItem(f"{tm:.2f} kg"))
            self._berechne()

    # ----------------------------------------------------------------
    # Berechnung
    # ----------------------------------------------------------------

    def _berechne(self):
        if not self._aktuelles_pferd:
            return

        p = self._aktuelles_pferd
        diag = [d.strip() for d in (p.get("diagnosen") or "").split(",") if d.strip()]

        pferde_param = PferdeParameter(
            gewicht_kg   = p["gewicht_kg"],
            alter_jahre  = p["alter_jahre"],
            rasse_typ    = p.get("rasse_typ", "Warmblut"),
            nutzung      = p.get("nutzung", "Freizeit"),
            geschlecht   = p.get("geschlecht", "Stute"),
            traechtigkeit= p.get("traechtigkeit", 0),
            laktation    = p.get("laktation", 0),
            diagnosen    = diag,
        )

        bedarf = berechne_bedarf(pferde_param)

        # Positions aufbauen
        positionen = []

        # Heu
        heu_q = self.heu_combo.currentData()
        heu_menge = self.heu_menge.value()
        if heu_q and heu_menge > 0:
            positionen.append(heu_als_position(heu_q, heu_menge))

        # Kraftfutter etc.
        for fm_daten, menge_kg in self._rations_positionen:
            positionen.append(position_aus_db_row(fm_daten, menge_kg))

        ist = berechne_ration(positionen)
        diff = berechne_differenz(ist, bedarf, diag)

        # Summen-Info
        gesamt_fm = heu_menge + sum(m for _, m in self._rations_positionen)
        self.summen_label.setText(
            f"Gesamt FM: {gesamt_fm:.1f} kg/Tag | "
            f"TS: {ist.trockenmasse_kg:.2f} kg/Tag | "
            f"Energie: {ist.energie_mj:.1f} MJ/Tag")

        # Vergleichstabelle aktualisieren
        self._befuelle_vergleich(bedarf, ist, diff)

        # Warnungen
        warnungen = []
        if diff.ts_ueberschreitung_pct > 120:
            warnungen.append(
                f"⚠ Trockenmasse-Überversorgung: Ist {ist.trockenmasse_kg:.1f} kg TS/Tag "
                f"= {diff.ts_ueberschreitung_pct:.0f}% des Bedarfs "
                f"(empfohlen: {bedarf.trockenmasse_kg:.1f} kg) – "
                f"Erhöhte Mineralwerte sind ein Mengenproblem, kein Überangebot!")
        if diff.nsc_uebersteigt_limit:
            warnungen.append(
                f"⚠ NSC-Gehalt {ist.nsc_pct_von_ts:.1f}% überschreitet Limit "
                f"{bedarf.nsc_max_pct:.0f}% der TS!")
        if diff.staerke_uebersteigt_limit:
            warnungen.append(
                f"⚠ Stärke {ist.staerke_pct_von_ts:.1f}% überschreitet Limit "
                f"{bedarf.stärke_max_pct:.0f}% der TS!")

        if warnungen:
            self.warn_label.setText("\n".join(warnungen))
            self.warn_label.setVisible(True)
        else:
            self.warn_label.setVisible(False)

        # Speichern für Export
        self._letzter_bedarf   = bedarf
        self._letztes_ist      = ist
        self._letzter_diff     = diff
        self._letzte_positionen= positionen

    def _befuelle_vergleich(self, bedarf, ist, diff):
        kennzahlen = [
            ("Trockenmasse", "kg/Tag",  bedarf.trockenmasse_kg, ist.trockenmasse_kg),
            ("Energie",      "MJ/Tag",  bedarf.energie_mj,      ist.energie_mj),
            ("Rohprotein",   "g/Tag",   bedarf.rp_g,            ist.rohprotein_g),
            ("Lysin",        "g/Tag",   bedarf.lysin_g,         ist.lysin_g),
            ("Rohfett",      "g/Tag",   None,                   ist.rohfett_g),
            ("Rohfaser",     "g/Tag",   None,                   ist.rohfaser_g),
            ("Stärke",       "% TS",    bedarf.stärke_max_pct,  ist.staerke_pct_von_ts),
            ("NSC",          "% TS",    bedarf.nsc_max_pct,     ist.nsc_pct_von_ts),
            (None, None, None, None),   # Trennzeile
            ("Calcium",      "g/Tag",   bedarf.calcium_g,       ist.calcium_g),
            ("Phosphor",     "g/Tag",   bedarf.phosphor_g,      ist.phosphor_g),
            ("Magnesium",    "g/Tag",   bedarf.magnesium_g,     ist.magnesium_g),
            ("Natrium",      "g/Tag",   bedarf.natrium_g,       ist.natrium_g),
            (None, None, None, None),
            ("Kupfer",       "mg/Tag",  bedarf.kupfer_mg,       ist.kupfer_mg),
            ("Zink",         "mg/Tag",  bedarf.zink_mg,         ist.zink_mg),
            ("Mangan",       "mg/Tag",  bedarf.mangan_mg,       ist.mangan_mg),
            ("Selen",        "mg/Tag",  bedarf.selen_mg,        ist.selen_mg),
            (None, None, None, None),
            ("Vitamin A",    "IE/Tag",  bedarf.vit_a_ie,        ist.vit_a_ie),
            ("Vitamin E",    "mg/Tag",  bedarf.vit_e_mg,        ist.vit_e_mg),
        ]

        self.vergleich_tabelle.setRowCount(0)

        for eintrag in kennzahlen:
            name, einheit, bed_val, ist_val = eintrag
            row = self.vergleich_tabelle.rowCount()
            self.vergleich_tabelle.insertRow(row)

            if name is None:
                # Trennzeile
                for col in range(6):
                    item = QTableWidgetItem("")
                    item.setBackground(QColor("#EEEEEE"))
                    self.vergleich_tabelle.setItem(row, col, item)
                self.vergleich_tabelle.setRowHeight(row, 6)
                continue

            self.vergleich_tabelle.setItem(row, 0, QTableWidgetItem(name))
            self.vergleich_tabelle.setItem(row, 1, QTableWidgetItem(einheit))

            if bed_val is not None:
                self.vergleich_tabelle.setItem(
                    row, 2, QTableWidgetItem(f"{bed_val:.2f}"))
            else:
                self.vergleich_tabelle.setItem(row, 2, QTableWidgetItem("–"))

            if ist_val is not None:
                ist_item = QTableWidgetItem(f"{ist_val:.2f}")
                self.vergleich_tabelle.setItem(row, 3, ist_item)
            else:
                self.vergleich_tabelle.setItem(row, 3, QTableWidgetItem("–"))

            if bed_val is not None and ist_val is not None and bed_val != 0:
                diff_val = ist_val - bed_val
                diff_item = QTableWidgetItem(f"{diff_val:+.2f}")

                # Farbgebung
                if abs(diff_val) < 0.01 * max(1, bed_val):
                    farbe = FARBE_OK
                elif diff_val < 0:
                    farbe = FARBE_MANGEL
                elif diff_val > 2 * max(1, bed_val):
                    farbe = FARBE_UEBER
                else:
                    farbe = FARBE_OK

                # NSC/Stärke: Limit-Logik umgekehrt
                if name in ("NSC", "Stärke") and bed_val > 0:
                    farbe = FARBE_MANGEL if diff_val > 0 else FARBE_OK

                diff_item.setBackground(QBrush(farbe))
                self.vergleich_tabelle.setItem(row, 4, diff_item)

                # Diff % Spalte
                diff_pct = (ist_val - bed_val) / bed_val * 100
                pct_item = QTableWidgetItem(f"{diff_pct:+.0f} %")
                pct_item.setBackground(QBrush(farbe))
                pct_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.vergleich_tabelle.setItem(row, 5, pct_item)
            elif bed_val is not None and ist_val is not None and bed_val == 0:
                # Bedarf = 0, trotzdem absolute Differenz zeigen
                diff_val = ist_val - bed_val
                self.vergleich_tabelle.setItem(row, 4, QTableWidgetItem(f"{diff_val:+.2f}"))
                self.vergleich_tabelle.setItem(row, 5, QTableWidgetItem("–"))
            else:
                self.vergleich_tabelle.setItem(row, 4, QTableWidgetItem(""))
                self.vergleich_tabelle.setItem(row, 5, QTableWidgetItem(""))

    # ----------------------------------------------------------------
    # Export
    # ----------------------------------------------------------------

    def _exportieren(self, format: str):
        if not hasattr(self, "_letzter_bedarf") or not self._aktuelles_pferd:
            QMessageBox.information(self, "Hinweis",
                "Bitte zuerst ein Pferd auswählen und die Ration berechnen.")
            return

        if format == "pdf":
            pfad, _ = QFileDialog.getSaveFileName(
                self, "PDF speichern", "", "PDF-Dateien (*.pdf)")
            if not pfad:
                return
            try:
                from export_module import export_pdf
                export_pdf(
                    self._aktuelles_pferd,
                    self._letzter_bedarf,
                    self._letztes_ist,
                    self._letzter_diff,
                    self._letzte_positionen,
                    pfad)
                QMessageBox.information(self, "Erfolg", f"PDF gespeichert:\n{pfad}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

        elif format == "xlsx":
            pfad, _ = QFileDialog.getSaveFileName(
                self, "Excel speichern", "", "Excel-Dateien (*.xlsx)")
            if not pfad:
                return
            try:
                from export_module import export_xlsx
                export_xlsx(
                    self._aktuelles_pferd,
                    self._letzter_bedarf,
                    self._letztes_ist,
                    self._letzter_diff,
                    self._letzte_positionen,
                    pfad)
                QMessageBox.information(self, "Erfolg", f"Excel gespeichert:\n{pfad}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    # ----------------------------------------------------------------
    # Optimierungsassistent
    # ----------------------------------------------------------------

    def _oeffne_optimierungsassistent(self):
        if not hasattr(self, "_letzter_bedarf") or not self._aktuelles_pferd:
            QMessageBox.information(
                self, "Hinweis",
                "Bitte zuerst ein Pferd auswählen und die Ration berechnen."
            )
            return

        heu_q    = self.heu_combo.currentData()
        heu_menge = self.heu_menge.value()

        # Basis-Positionen als (dict, menge_kg) für den Dialog aufbereiten
        basis_pos = [(fm, menge) for fm, menge in self._rations_positionen]

        dlg = OptimierungsDialog(
            pferd            = self._aktuelles_pferd,
            ist              = self._letztes_ist,
            bedarf           = self._letzter_bedarf,
            heu_menge_kg     = heu_menge,
            heu_qualitaet    = heu_q,
            basis_positionen = basis_pos,
            parent           = self,
        )
        dlg.exec()
