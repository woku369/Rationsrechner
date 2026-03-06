"""
Optimierungsassistent – Dialog für Defizitanalyse, Supplementvorschläge und Variantenvergleich.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDoubleSpinBox, QSplitter, QScrollArea, QWidget, QFrame,
    QGroupBox, QLineEdit, QTextEdit, QTabWidget, QListWidget,
    QListWidgetItem, QMessageBox, QSizePolicy, QAbstractItemView,
    QSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon

import database
from bedarfsberechnung import Bedarfswerte
from rationsrechner import RationsErgebnis, heu_als_position, position_aus_db_row
from optimierung import (
    generiere_vorschlaege, supplement_als_position,
    berechne_variante_ergebnis, NAEHRSTOFFE,
    Vorschlag, FutteranpassungVorschlag,
)

# ── Farben ──
C_DEFIZIT   = QColor("#F8D7DA")
C_UEBER     = QColor("#FFF3CD")
C_OK        = QColor("#D4EDDA")
C_HEADER    = QColor("#2E4057")
C_SUPPL     = QColor("#E8F4FD")


class OptimierungsDialog(QDialog):
    """Hauptdialog des Optimierungsassistenten."""

    def __init__(self, pferd: dict, ist: RationsErgebnis, bedarf: Bedarfswerte,
                 heu_menge_kg: float = 0.0,
                 heu_qualitaet: dict | None = None,
                 basis_positionen: list | None = None,
                 parent=None):
        """
        pferd:            dict mit Pferd-Datenbankzeile
        ist:              aktuelles Rations-Ergebnis
        bedarf:           berechneter Tagesbedarf
        heu_menge_kg:     aktuelle Heumenge in kg
        heu_qualitaet:    dict der aktuellen Heu-Qualität (oder None)
        basis_positionen: list of (db_row_dict, menge_kg) – aktuelle Rations-Positionen
        """
        super().__init__(parent)
        self._pferd           = pferd
        self._ist             = ist
        self._bedarf          = bedarf
        self._heu_menge_kg    = heu_menge_kg
        self._heu_qualitaet   = heu_qualitaet
        self._basis_pos       = basis_positionen or []

        # Lazyload Stammdaten
        self._alle_fm         = database.alle_futtermittel()
        self._alle_supps      = database.alle_supplemente()
        self._heu_qualitaeten = database.heu_qualitaeten()
        self._varianten       = []          # aus DB
        self._aktuelle_var_id = None        # aktuell im Editor

        # Vorschläge berechnen
        self._vorschlaege, self._anpassungen = generiere_vorschlaege(
            ist, bedarf, heu_menge_kg
        )

        self.setWindowTitle(f"Optimierungsassistent – {pferd.get('name', '')}")
        self.resize(1200, 780)
        self._setup_ui()
        self._lade_varianten()

    # ──────────────────────────────────────────────────────────────
    # UI Aufbau
    # ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Kopfzeile ──
        header = self._baue_header()
        layout.addLayout(header)

        # ── Tab-Widget ──
        tabs = QTabWidget()
        tabs.addTab(self._baue_analyse_tab(), "🔍 Analyse & Vorschläge")
        tabs.addTab(self._baue_varianten_tab(), "🧮 Varianten")
        tabs.addTab(self._baue_vergleich_tab(), "📊 Vergleich")
        self._tabs = tabs
        layout.addWidget(tabs, stretch=1)

        # ── Buttons unten ──
        btn_lo = QHBoxLayout()
        btn_lo.addStretch()
        btn_schliessen = QPushButton("Schließen")
        btn_schliessen.clicked.connect(self.close)
        btn_lo.addWidget(btn_schliessen)
        layout.addLayout(btn_lo)

    def _baue_header(self) -> QHBoxLayout:
        lo = QHBoxLayout()
        pferd_name = self._pferd.get("name", "")
        kgw = self._pferd.get("gewicht_kg", 0)
        nutzung = self._pferd.get("nutzung", "")

        lbl = QLabel(f"<b>{pferd_name}</b>  |  {kgw:.0f} kg  |  {nutzung}")
        lbl.setObjectName("section_title")
        lo.addWidget(lbl)

        # Kurzzusammenfassung
        n_def = sum(1 for v in self._vorschlaege if v.typ == "Defizit")
        n_ue  = sum(1 for v in self._vorschlaege if v.typ == "Überversorgung")
        farbe = "#F8D7DA" if n_def > 0 else ("#FFF3CD" if n_ue > 0 else "#D4EDDA")
        status_text = []
        if n_def:  status_text.append(f"🔴 {n_def} Defizit{'e' if n_def>1 else ''}")
        if n_ue:   status_text.append(f"🟡 {n_ue} Überschuss{'e' if n_ue>1 else ''}")
        if not status_text: status_text.append("✅ Alle Nährstoffe im Rahmen")

        summary = QLabel("  |  ".join(status_text))
        summary.setStyleSheet(f"background:{farbe}; padding:4px 10px; border-radius:4px;")
        lo.addWidget(summary)
        lo.addStretch()
        return lo

    # ── Tab 1: Analyse ──────────────────────────────────────────

    def _baue_analyse_tab(self) -> QWidget:
        widget = QWidget()
        lo = QHBoxLayout(widget)
        lo.setContentsMargins(5, 5, 5, 5)
        lo.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Links: IST/SOLL Tabelle
        links = self._baue_ist_soll_tabelle()
        splitter.addWidget(links)

        # Rechts: Vorschläge
        rechts = self._baue_vorschlag_panel()
        splitter.addWidget(rechts)

        splitter.setSizes([420, 760])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        lo.addWidget(splitter)
        return widget

    def _baue_ist_soll_tabelle(self) -> QWidget:
        grp = QGroupBox("Nährstoff-Übersicht: Bedarf vs. IST")
        lo = QVBoxLayout(grp)
        lo.setContentsMargins(5, 8, 5, 5)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["Nährstoff", "Bedarf", "IST", "Diff%", ""])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(48)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setAlternatingRowColors(True)

        for ist_feld, bed_feld, anzeige, einheit, _, _ in NAEHRSTOFFE:
            ist_val = getattr(self._ist, ist_feld, 0.0) or 0.0
            bed_val = getattr(self._bedarf, bed_feld, 0.0) or 0.0
            if bed_val <= 0:
                continue

            diff_pct = (ist_val - bed_val) / bed_val * 100  # negativ = Defizit
            row = tbl.rowCount()
            tbl.insertRow(row)

            # Farbe
            if diff_pct < -5:
                farbe = C_DEFIZIT
                icon  = "🔴"
            elif diff_pct > 50:
                farbe = C_UEBER
                icon  = "🟡"
            else:
                farbe = C_OK
                icon  = "✅"

            # Formatierung
            if einheit in ("IE",):
                bed_str = f"{bed_val:,.0f} {einheit}"
                ist_str = f"{ist_val:,.0f} {einheit}"
            elif einheit == "µg":
                bed_str = f"{bed_val:.0f} {einheit}"
                ist_str = f"{ist_val:.0f} {einheit}"
            elif bed_val >= 100:
                bed_str = f"{bed_val:.0f} {einheit}"
                ist_str = f"{ist_val:.0f} {einheit}"
            else:
                bed_str = f"{bed_val:.2f} {einheit}"
                ist_str = f"{ist_val:.2f} {einheit}"

            for col, txt in enumerate([anzeige, bed_str, ist_str,
                                        f"{diff_pct:+.0f}%", icon]):
                item = QTableWidgetItem(txt)
                item.setBackground(QBrush(farbe))
                if col in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tbl.setItem(row, col, item)

        tbl.resizeRowsToContents()
        lo.addWidget(tbl)
        return grp

    def _baue_vorschlag_panel(self) -> QWidget:
        """Rechtes Panel: Vorschlagskarten pro Nährstoff."""
        outer = QWidget()
        outer_lo = QVBoxLayout(outer)
        outer_lo.setContentsMargins(0, 0, 0, 0)
        outer_lo.setSpacing(0)

        header = QLabel("Korrekturvorschläge")
        header.setObjectName("section_title")
        outer_lo.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_lo = QVBoxLayout(inner)
        inner_lo.setContentsMargins(4, 4, 4, 4)
        inner_lo.setSpacing(6)

        if not self._vorschlaege and not self._anpassungen:
            lbl = QLabel("✅ Keine wesentlichen Abweichungen festgestellt.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_lo.addWidget(lbl)
        else:
            # Futteranpassungen zuerst
            if self._anpassungen:
                grp = QGroupBox("Mengenkorrekturen (Heu / Kraftfutter)")
                grp_lo = QVBoxLayout(grp)
                for anp in self._anpassungen:
                    lbl = QLabel(f"  ⚙️  {anp.begruendung}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet("padding:4px; background:#FFF3CD; border-radius:3px;")
                    grp_lo.addWidget(lbl)
                inner_lo.addWidget(grp)

            # Defizite
            defizite = [v for v in self._vorschlaege if v.typ == "Defizit"]
            ueberschuesse = [v for v in self._vorschlaege if v.typ == "Überversorgung"]

            if defizite:
                grp_def = QGroupBox(f"🔴 Defizite ({len(defizite)})")
                grp_def_lo = QVBoxLayout(grp_def)
                grp_def_lo.setSpacing(6)
                for v in defizite:
                    karte = self._baue_vorschlag_karte(v)
                    grp_def_lo.addWidget(karte)
                inner_lo.addWidget(grp_def)

            if ueberschuesse:
                grp_ue = QGroupBox(f"🟡 Überschüsse ({len(ueberschuesse)})")
                grp_ue_lo = QVBoxLayout(grp_ue)
                for v in ueberschuesse:
                    karte = self._baue_vorschlag_karte(v)
                    grp_ue_lo.addWidget(karte)
                inner_lo.addWidget(grp_ue)

        # Variante erstellen-Button
        if self._vorschlaege:
            btn_variante = QPushButton("🧮 Aus Vorschlägen neue Variante erstellen")
            btn_variante.setStyleSheet(
                "background:#2E4057; color:white; padding:6px; border-radius:4px;"
            )
            btn_variante.clicked.connect(self._vorschlaege_als_variante)
            inner_lo.addWidget(btn_variante)

        inner_lo.addStretch()
        scroll.setWidget(inner)
        outer_lo.addWidget(scroll, stretch=1)
        return outer

    def _baue_vorschlag_karte(self, v: Vorschlag) -> QFrame:
        """Eine einzelne Vorschlags-Karte."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        bg = "#F8D7DA" if v.typ == "Defizit" else "#FFF3CD"
        frame.setStyleSheet(f"QFrame {{ background:{bg}; border-radius:5px; padding:4px; }}")

        lo = QVBoxLayout(frame)
        lo.setContentsMargins(8, 6, 8, 6)
        lo.setSpacing(4)

        # Zeile 1: Nährstoff + Werte
        row1 = QHBoxLayout()
        icon = "🔴" if v.typ == "Defizit" else "🟡"
        name_lbl = QLabel(f"{icon} <b>{v.anzeige_name}</b>")
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        row1.addWidget(name_lbl)
        row1.addStretch()

        # IST / SOLL
        def fmt(val, einheit):
            if val >= 1000:
                return f"{val:,.0f} {einheit}"
            elif val >= 10:
                return f"{val:.1f} {einheit}"
            else:
                return f"{val:.3f} {einheit}"

        vals = QLabel(
            f"IST: {fmt(v.ist, v.einheit)}  |  "
            f"Bedarf: {fmt(v.bedarf, v.einheit)}  |  "
            f"<b>{abs(v.differenz_pct):.0f}%</b> {'Defizit' if v.typ=='Defizit' else 'Überschuss'}"
        )
        vals.setTextFormat(Qt.TextFormat.RichText)
        row1.addWidget(vals)
        lo.addLayout(row1)

        # Zeile 2: Supplement-Auswahl (nur bei Defiziten)
        if v.typ == "Defizit" and v.supplemente:
            supp_row = QHBoxLayout()
            supp_row.addWidget(QLabel("Supplement:"))

            combo = QComboBox()
            combo.setMinimumWidth(220)
            for s in v.supplemente:
                combo.addItem(s["name"], s)
            supp_row.addWidget(combo)

            supp_row.addWidget(QLabel("Dosis (g/Tag):"))
            spin = QDoubleSpinBox()
            spin.setRange(0.001, 9999.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(round(v.empfohlene_dosis_g, 3))
            spin.setFixedWidth(90)

            # Dosis neu berechnen wenn Supplement gewechselt
            def _update_dosis(idx, _v=v, _combo=combo, _spin=spin):
                supp = _combo.itemData(idx)
                if supp:
                    konz = supp.get("konzentration_je_kg", 1.0)
                    if konz > 0:
                        neue_dosis = (_v.differenz / konz) * 1000
                        max_d = supp.get("max_tagesdosis_einheit")
                        if max_d and neue_dosis * konz / 1000 > max_d:
                            neue_dosis = max_d / konz * 1000
                        _spin.setValue(round(max(0.001, neue_dosis), 3))

            combo.currentIndexChanged.connect(_update_dosis)
            supp_row.addWidget(spin)

            btn_add = QPushButton("➕ In Variante")
            btn_add.setToolTip("Supplement in einer neuen oder bestehenden Variante vormerken")
            btn_add.clicked.connect(
                lambda _, c=combo, sp=spin: self._supplement_vormerken(c, sp)
            )
            supp_row.addWidget(btn_add)
            supp_row.addStretch()
            lo.addLayout(supp_row)

        # Zeile 3: Hinweistext (klein, grau)
        if v.hinweis:
            hint = QLabel(v.hinweis)
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#555; font-size:10px;")
            lo.addWidget(hint)

        return frame

    # ── Tab 2: Varianten ────────────────────────────────────────

    def _baue_varianten_tab(self) -> QWidget:
        widget = QWidget()
        lo = QHBoxLayout(widget)
        lo.setContentsMargins(5, 5, 5, 5)
        lo.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Links: Varianten-Liste
        links = self._baue_varianten_liste()
        splitter.addWidget(links)

        # Rechts: Varianten-Editor
        rechts = self._baue_varianten_editor()
        splitter.addWidget(rechts)

        splitter.setSizes([280, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        lo.addWidget(splitter)
        return widget

    def _baue_varianten_liste(self) -> QGroupBox:
        grp = QGroupBox("Gespeicherte Varianten")
        lo = QVBoxLayout(grp)

        self._var_list = QListWidget()
        self._var_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._var_list.currentRowChanged.connect(self._variante_gewaehlt)
        lo.addWidget(self._var_list)

        btn_row = QHBoxLayout()
        btn_neu = QPushButton("➕ Neu")
        btn_kop = QPushButton("📋 Kopie")
        btn_del = QPushButton("🗑 Löschen")
        btn_neu.clicked.connect(self._neue_variante)
        btn_kop.clicked.connect(self._variante_kopieren)
        btn_del.clicked.connect(self._variante_loeschen)
        btn_row.addWidget(btn_neu)
        btn_row.addWidget(btn_kop)
        btn_row.addWidget(btn_del)
        lo.addLayout(btn_row)
        return grp

    def _baue_varianten_editor(self) -> QGroupBox:
        grp = QGroupBox("Variante bearbeiten")
        lo = QVBoxLayout(grp)
        lo.setSpacing(6)

        # Name + Beschreibung
        meta_lo = QHBoxLayout()
        meta_lo.addWidget(QLabel("Name:"))
        self._var_name = QLineEdit()
        self._var_name.setPlaceholderText("z.B. '+Selen +Vit.E'")
        meta_lo.addWidget(self._var_name, stretch=1)
        meta_lo.addWidget(QLabel("Notiz:"))
        self._var_beschr = QLineEdit()
        self._var_beschr.setPlaceholderText("Kurze Beschreibung …")
        meta_lo.addWidget(self._var_beschr, stretch=2)
        lo.addLayout(meta_lo)

        # Positionen-Tabelle
        self._var_tbl = QTableWidget()
        self._var_tbl.setColumnCount(4)
        self._var_tbl.setHorizontalHeaderLabels(["Typ", "Futtermittel / Supplement", "Menge", ""])
        self._var_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._var_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._var_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._var_tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._var_tbl.verticalHeader().setVisible(False)
        self._var_tbl.verticalHeader().setDefaultSectionSize(48)
        self._var_tbl.setAlternatingRowColors(True)
        lo.addWidget(self._var_tbl, stretch=1)

        # Hinzufügen-Buttons
        add_lo = QHBoxLayout()
        btn_add_fm  = QPushButton("➕ Heu / Kraftfutter")
        btn_add_sup = QPushButton("💊 Supplement")
        btn_add_fm.clicked.connect(self._popup_futtermittel_hinzufuegen)
        btn_add_sup.clicked.connect(self._popup_supplement_hinzufuegen)
        add_lo.addWidget(btn_add_fm)
        add_lo.addWidget(btn_add_sup)
        add_lo.addStretch()
        lo.addLayout(add_lo)

        # Mini-Ergebnis
        self._var_ergebnis_lbl = QLabel("")
        self._var_ergebnis_lbl.setWordWrap(True)
        self._var_ergebnis_lbl.setStyleSheet(
            "background:#F0F0F0; padding:6px; border-radius:4px; font-size:11px;"
        )
        lo.addWidget(self._var_ergebnis_lbl)

        # Speichern + Berechnen
        save_lo = QHBoxLayout()
        btn_ber  = QPushButton("🔄 Berechnen")
        btn_save = QPushButton("💾 Speichern")
        btn_ber.clicked.connect(self._variante_berechnen)
        btn_save.clicked.connect(self._variante_speichern)
        save_lo.addStretch()
        save_lo.addWidget(btn_ber)
        save_lo.addWidget(btn_save)
        lo.addLayout(save_lo)
        return grp

    # ── Tab 3: Vergleich ────────────────────────────────────────

    def _baue_vergleich_tab(self) -> QWidget:
        widget = QWidget()
        lo = QVBoxLayout(widget)
        lo.setContentsMargins(5, 5, 5, 5)

        info = QLabel(
            "Wähle bis zu 3 Varianten zum Vergleich. "
            "Die aktuelle Ration wird immer als Basis angezeigt."
        )
        info.setWordWrap(True)
        lo.addWidget(info)

        # Varianten auswählen
        sel_lo = QHBoxLayout()
        sel_lo.addWidget(QLabel("Varianten:"))
        self._vgl_combo1 = QComboBox()
        self._vgl_combo2 = QComboBox()
        self._vgl_combo3 = QComboBox()
        for combo in (self._vgl_combo1, self._vgl_combo2, self._vgl_combo3):
            combo.addItem("— keine —", None)
        sel_lo.addWidget(self._vgl_combo1)
        sel_lo.addWidget(self._vgl_combo2)
        sel_lo.addWidget(self._vgl_combo3)
        btn_vgl = QPushButton("📊 Vergleich aktualisieren")
        btn_vgl.clicked.connect(self._vergleich_aktualisieren)
        sel_lo.addWidget(btn_vgl)
        sel_lo.addStretch()
        lo.addLayout(sel_lo)

        # Vergleichstabelle
        self._vgl_tbl = QTableWidget()
        self._vgl_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._vgl_tbl.setAlternatingRowColors(True)
        self._vgl_tbl.verticalHeader().setVisible(False)
        self._vgl_tbl.verticalHeader().setDefaultSectionSize(48)
        lo.addWidget(self._vgl_tbl, stretch=1)

        # Export
        exp_lo = QHBoxLayout()
        exp_lo.addStretch()
        btn_xlsx = QPushButton("📊 Excel exportieren")
        btn_xlsx.clicked.connect(self._export_vergleich_xlsx)
        exp_lo.addWidget(btn_xlsx)
        lo.addLayout(exp_lo)
        return widget

    # ──────────────────────────────────────────────────────────────
    # Logik: Varianten
    # ──────────────────────────────────────────────────────────────

    def _lade_varianten(self):
        pferd_id = self._pferd.get("id")
        if not pferd_id:
            return
        self._varianten = database.alle_varianten_fuer_pferd(pferd_id)
        self._var_list.clear()

        for combo in (self._vgl_combo1, self._vgl_combo2, self._vgl_combo3):
            combo.clear()
            combo.addItem("— keine —", None)

        for v in self._varianten:
            item = QListWidgetItem(v["name"])
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            self._var_list.addItem(item)

            for combo in (self._vgl_combo1, self._vgl_combo2, self._vgl_combo3):
                combo.addItem(v["name"], v["id"])

    def _variante_gewaehlt(self, row: int):
        if row < 0 or row >= len(self._varianten):
            return
        var_data = database.lade_variante(self._varianten[row]["id"])
        if not var_data:
            return
        v = var_data["variante"]
        self._aktuelle_var_id = v["id"]
        self._var_name.setText(v.get("name", ""))
        self._var_beschr.setText(v.get("beschreibung", "") or "")
        self._var_tbl.setRowCount(0)
        for pos in var_data["positionen"]:
            self._var_tbl_zeile_hinzufuegen(pos)
        self._variante_berechnen()

    def _neue_variante(self):
        """Leere neue Variante mit Basis der aktuellen Ration vorbefüllen."""
        self._aktuelle_var_id = None
        self._var_name.setText("Neue Variante")
        self._var_beschr.setText("")
        self._var_tbl.setRowCount(0)

        # Heu aus Basis übernehmen
        if self._heu_qualitaet:
            self._var_tbl_zeile_hinzufuegen({
                "quell_typ": "heu",
                "heu_qualitaet_id": self._heu_qualitaet["id"],
                "_heu_bezeichnung": self._heu_qualitaet.get("bezeichnung", "Heu"),
                "menge_kg": self._heu_menge_kg,
            })

        # Kraftfutter aus Basis übernehmen
        for pos_row, menge in self._basis_pos:
            self._var_tbl_zeile_hinzufuegen({
                "quell_typ": "futtermittel",
                "futtermittel_id": pos_row.get("id"),
                "_fm_name": pos_row.get("name", ""),
                "menge_kg": menge,
            })
        self._variante_berechnen()

    def _variante_kopieren(self):
        row = self._var_list.currentRow()
        if row < 0:
            self._neue_variante()
            return
        # Statt Datenbankzustand benutzen wir was im Editor steht
        self._aktuelle_var_id = None
        aktuell = self._var_name.text()
        self._var_name.setText(f"{aktuell} (Kopie)")

    def _variante_loeschen(self):
        row = self._var_list.currentRow()
        if row < 0 or row >= len(self._varianten):
            return
        vid = self._varianten[row]["id"]
        r = QMessageBox.question(
            self, "Variante löschen",
            f"Variante '{self._varianten[row]['name']}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            database.loesche_variante(vid)
            self._lade_varianten()
            self._var_tbl.setRowCount(0)
            self._var_ergebnis_lbl.setText("")

    def _variante_speichern(self):
        pferd_id = self._pferd.get("id")
        name = self._var_name.text().strip() or "Variante"
        beschr = self._var_beschr.text().strip()
        positionen = self._editor_positionen_lesen()

        vid = database.speichere_variante(
            pferd_id, name, beschr, positionen, self._aktuelle_var_id
        )
        self._aktuelle_var_id = vid
        self._lade_varianten()
        QMessageBox.information(self, "Gespeichert", f"Variante '{name}' wurde gespeichert.")

    def _variante_berechnen(self):
        """Berechnet das aktuelle Ration-Ergebnis des Editors und zeigt Kurzübersicht."""
        positionen = self._editor_positionen_lesen()
        fm_lookup    = {fm["id"]: fm for fm in self._alle_fm}
        supp_lookup  = {s["id"]: s  for s in self._alle_supps}
        heu_lookup   = {h["id"]: h  for h in self._heu_qualitaeten}

        erg = berechne_variante_ergebnis(positionen, fm_lookup, supp_lookup, heu_lookup)

        # Kurzübersicht
        bed = self._bedarf
        lines = []
        pairs = [
            ("Energie", erg.energie_mj,   bed.energie_mj,   "MJ"),
            ("RP",      erg.rohprotein_g, bed.rp_g,         "g"),
            ("Lysin",   erg.lysin_g,      bed.lysin_g,       "g"),
            ("Kupfer",  erg.kupfer_mg,    bed.kupfer_mg,    "mg"),
            ("Zink",    erg.zink_mg,      bed.zink_mg,      "mg"),
            ("Selen",   erg.selen_mg,     bed.selen_mg,     "mg"),
            ("Vit. E",  erg.vit_e_mg,     bed.vit_e_mg,     "mg"),
        ]
        for name, ist_v, bed_v, einh in pairs:
            if bed_v and bed_v > 0:
                pct = (ist_v - bed_v) / bed_v * 100
                icon = "✅" if abs(pct) <= 20 else ("🔴" if pct < 0 else "🟡")
                lines.append(f"{icon} {name}: {ist_v:.2g} {einh}  ({pct:+.0f}%)")

        self._var_ergebnis_lbl.setText("   ".join(lines[:4]) + "\n" + "   ".join(lines[4:]))

    def _editor_positionen_lesen(self) -> list:
        """Liest die aktuellen Positionen aus der Editor-Tabelle."""
        positionen = []
        for row in range(self._var_tbl.rowCount()):
            typ_item  = self._var_tbl.item(row, 0)
            data_item = self._var_tbl.item(row, 1)
            menge_wid = self._var_tbl.cellWidget(row, 2)
            if not typ_item or not data_item:
                continue
            pos = {
                "quell_typ": typ_item.data(Qt.ItemDataRole.UserRole),
                "futtermittel_id": None,
                "supplement_id": None,
                "heu_qualitaet_id": None,
                "menge_kg": menge_wid.value() if menge_wid else 0.0,
            }
            source_id = data_item.data(Qt.ItemDataRole.UserRole)
            quell_typ = pos["quell_typ"]
            if quell_typ == "futtermittel":
                pos["futtermittel_id"] = source_id
            elif quell_typ == "supplement":
                pos["supplement_id"] = source_id
                # Supplement-Dosis ist in g → umrechnen in kg für DB
                pos["menge_kg"] = (menge_wid.value() if menge_wid else 0.0) / 1000.0
            elif quell_typ == "heu":
                pos["heu_qualitaet_id"] = source_id
            positionen.append(pos)
        return positionen

    def _var_tbl_zeile_hinzufuegen(self, pos: dict):
        """Fügt eine Zeile zur Varianten-Tabelle hinzu."""
        row = self._var_tbl.rowCount()
        self._var_tbl.insertRow(row)

        typ = pos.get("quell_typ", "")
        typ_labels = {"futtermittel": "Kraftfutter/FM", "supplement": "💊 Supplement", "heu": "🌾 Heu"}
        typ_item = QTableWidgetItem(typ_labels.get(typ, typ))
        typ_item.setData(Qt.ItemDataRole.UserRole, typ)

        # Name aus verschiedenen Quellen ermitteln
        if typ == "futtermittel":
            fm_id = pos.get("futtermittel_id")
            name = pos.get("_fm_name") or next(
                (fm["name"] for fm in self._alle_fm if fm["id"] == fm_id), str(fm_id)
            )
            source_id = fm_id
        elif typ == "supplement":
            s_id = pos.get("supplement_id")
            name = pos.get("_supp_name") or next(
                (s["name"] for s in self._alle_supps if s["id"] == s_id), str(s_id)
            )
            source_id = s_id
        elif typ == "heu":
            h_id = pos.get("heu_qualitaet_id")
            name = pos.get("_heu_bezeichnung") or next(
                (h["bezeichnung"] for h in self._heu_qualitaeten if h["id"] == h_id), str(h_id)
            )
            source_id = h_id
        else:
            name, source_id = str(pos), None

        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, source_id)

        # Menge-SpinBox
        spin = QDoubleSpinBox()
        spin.setDecimals(3 if typ == "supplement" else 2)
        spin.setSuffix(" g/Tag" if typ == "supplement" else " kg/Tag")
        if typ == "supplement":
            spin.setRange(0.001, 999.0)
            # DB speichert kg; Position hat ggf. "menge_kg" die bereits kg ist
            menge_raw = pos.get("menge_kg", 0.0) or 0.0
            spin.setValue(menge_raw * 1000.0 if menge_raw < 1.0 else menge_raw)
        else:
            spin.setRange(0.01, 200.0)
            spin.setValue(pos.get("menge_kg", 0.0) or 0.0)

        # Löschen-Button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(34, 34)
        del_btn.setStyleSheet(
            "QPushButton { background:#e53935; color:white; border-radius:5px; "
            "font-weight:bold; font-size:14px; }"
            "QPushButton:hover { background:#c62828; }"
        )
        del_btn.clicked.connect(lambda _, r=row: self._var_zeile_loeschen(r))

        self._var_tbl.setItem(row, 0, typ_item)
        self._var_tbl.setItem(row, 1, name_item)
        self._var_tbl.setCellWidget(row, 2, spin)
        self._var_tbl.setCellWidget(row, 3, del_btn)
        self._var_tbl.setRowHeight(row, 48)

    def _var_zeile_loeschen(self, row: int):
        # Zeile nach aktuellem Index finden (falls sich Reihenfolge geändert hat)
        btn = self.sender()
        for r in range(self._var_tbl.rowCount()):
            wid = self._var_tbl.cellWidget(r, 3)
            if wid is btn:
                self._var_tbl.removeRow(r)
                return

    def _popup_futtermittel_hinzufuegen(self):
        """Mini-Dialog zum Hinzufügen von Heu oder Futtermittel zur Variante."""
        dlg = _AddFuttermittelDialog(self._alle_fm, self._heu_qualitaeten, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pos = dlg.ergebnis()
            if pos:
                self._var_tbl_zeile_hinzufuegen(pos)

    def _popup_supplement_hinzufuegen(self):
        """Mini-Dialog zum Hinzufügen eines Supplements zur Variante."""
        dlg = _AddSupplementDialog(self._alle_supps, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pos = dlg.ergebnis()
            if pos:
                self._var_tbl_zeile_hinzufuegen(pos)

    def _supplement_vormerken(self, combo: QComboBox, spin: QDoubleSpinBox):
        """Aus Vorschlags-Panel: Supplement zur aktuellen Variante im Editor vormerken."""
        supp = combo.currentData()
        if not supp:
            return
        dosis_g = spin.value()
        # In den Varianten-Tab wechseln
        self._tabs.setCurrentIndex(1)
        # Falls noch kein Editor-Inhalt: neue Variante vorbereiten
        if self._var_tbl.rowCount() == 0:
            self._neue_variante()
        # Supplement-Zeile hinzufügen
        self._var_tbl_zeile_hinzufuegen({
            "quell_typ": "supplement",
            "supplement_id": supp["id"],
            "_supp_name": supp["name"],
            "menge_kg": dosis_g / 1000.0,
        })
        self._variante_berechnen()

    def _vorschlaege_als_variante(self):
        """Erstellt automatisch eine neue Variante aus allen Defizit-Vorschlägen."""
        self._neue_variante()
        for v in self._vorschlaege:
            if v.typ == "Defizit" and v.supplemente and v.empfohlene_dosis_g > 0:
                s = v.supplemente[0]
                self._var_tbl_zeile_hinzufuegen({
                    "quell_typ": "supplement",
                    "supplement_id": s["id"],
                    "_supp_name": s["name"],
                    "menge_kg": v.empfohlene_dosis_g / 1000.0,
                })
        self._var_name.setText("Vorschlag-Auto")
        self._tabs.setCurrentIndex(1)
        self._variante_berechnen()

    # ──────────────────────────────────────────────────────────────
    # Vergleich-Tab Logik
    # ──────────────────────────────────────────────────────────────

    def _vergleich_aktualisieren(self):
        """Baut Vergleichstabelle zwischen Aktuell + bis zu 3 gespeicherten Varianten."""
        fm_lookup   = {fm["id"]: fm for fm in self._alle_fm}
        supp_lookup = {s["id"]: s   for s in self._alle_supps}
        heu_lookup  = {h["id"]: h   for h in self._heu_qualitaeten}

        # Spalten: Nährstoff + Bedarf + Aktuell + Variante1 + Variante2 + Variante3
        spalten = ["Nährstoff", "Einheit", "Bedarf", "Aktuell (IST)"]
        ergebnisse = []   # list of RationsErgebnis

        for combo in (self._vgl_combo1, self._vgl_combo2, self._vgl_combo3):
            vid = combo.currentData()
            if not vid:
                continue
            vdata = database.lade_variante(vid)
            if vdata:
                erg = berechne_variante_ergebnis(
                    vdata["positionen"], fm_lookup, supp_lookup, heu_lookup
                )
                ergebnisse.append((vdata["variante"]["name"], erg))
                spalten.append(vdata["variante"]["name"])

        tbl = self._vgl_tbl
        tbl.setColumnCount(len(spalten))
        tbl.setHorizontalHeaderLabels(spalten)
        tbl.setRowCount(0)

        for ist_feld, bed_feld, anzeige, einheit, _, _ in NAEHRSTOFFE:
            bed_val   = getattr(self._bedarf, bed_feld, 0.0) or 0.0
            ist_val   = getattr(self._ist,    ist_feld, 0.0) or 0.0
            if bed_val <= 0:
                continue

            row = tbl.rowCount()
            tbl.insertRow(row)

            def mk(txt, farbe=None):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if farbe:
                    it.setBackground(QBrush(farbe))
                return it

            def fmt_pct(val, bed):
                if bed <= 0:
                    return "—"
                p = (val - bed) / bed * 100
                return f"{p:+.0f}%"

            def farbe_pct(val, bed):
                if bed <= 0: return None
                p = (val - bed) / bed * 100
                if p < -5: return C_DEFIZIT
                if p > 50: return C_UEBER
                return C_OK

            tbl.setItem(row, 0, QTableWidgetItem(anzeige))
            tbl.setItem(row, 1, QTableWidgetItem(einheit))
            tbl.setItem(row, 2, mk(f"{bed_val:.2g}"))
            tbl.setItem(row, 3, mk(fmt_pct(ist_val, bed_val), farbe_pct(ist_val, bed_val)))

            for col_idx, (_, erg) in enumerate(ergebnisse):
                v_val = getattr(erg, ist_feld, 0.0) or 0.0
                tbl.setItem(row, 4 + col_idx,
                             mk(fmt_pct(v_val, bed_val), farbe_pct(v_val, bed_val)))

        tbl.resizeColumnsToContents()
        tbl.resizeRowsToContents()

    def _export_vergleich_xlsx(self):
        from PyQt6.QtWidgets import QFileDialog
        from export_module import exportiere_vergleich_xlsx
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel speichern", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"

        fm_lookup   = {fm["id"]: fm for fm in self._alle_fm}
        supp_lookup = {s["id"]: s   for s in self._alle_supps}
        heu_lookup  = {h["id"]: h   for h in self._heu_qualitaeten}

        varianten_ergebnisse = []
        for combo in (self._vgl_combo1, self._vgl_combo2, self._vgl_combo3):
            vid = combo.currentData()
            if not vid:
                continue
            vdata = database.lade_variante(vid)
            if vdata:
                erg = berechne_variante_ergebnis(
                    vdata["positionen"], fm_lookup, supp_lookup, heu_lookup
                )
                varianten_ergebnisse.append((vdata["variante"]["name"], erg))

        try:
            exportiere_vergleich_xlsx(
                path, self._pferd, self._bedarf,
                [("Aktuell (IST)", self._ist)] + varianten_ergebnisse
            )
            QMessageBox.information(self, "Exportiert", f"Gespeichert: {path}")
        except Exception as ex:
            QMessageBox.warning(self, "Fehler", str(ex))


# ──────────────────────────────────────────────────────────────────────────────
# Hilfs-Dialoge
# ──────────────────────────────────────────────────────────────────────────────

class _AddFuttermittelDialog(QDialog):
    """Mini-Dialog zum Hinzufügen von Heu oder Futtermittel."""

    def __init__(self, alle_fm: list, heu_qualitaeten: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Futtermittel / Heu hinzufügen")
        self.resize(400, 160)
        self._result_pos = None

        lo = QVBoxLayout(self)

        typ_row = QHBoxLayout()
        typ_row.addWidget(QLabel("Typ:"))
        self._typ_combo = QComboBox()
        self._typ_combo.addItem("🌾 Heu", "heu")
        self._typ_combo.addItem("Futtermittel", "futtermittel")
        self._typ_combo.currentIndexChanged.connect(self._typ_geaendert)
        typ_row.addWidget(self._typ_combo)
        lo.addLayout(typ_row)

        auswahl_row = QHBoxLayout()
        auswahl_row.addWidget(QLabel("Wahl:"))
        self._auswahl_combo = QComboBox()
        self._auswahl_combo.setMinimumWidth(240)
        auswahl_row.addWidget(self._auswahl_combo)
        lo.addLayout(auswahl_row)

        self._heu_qlt  = heu_qualitaeten
        self._alle_fm  = alle_fm

        menge_row = QHBoxLayout()
        menge_row.addWidget(QLabel("Menge:"))
        self._menge_spin = QDoubleSpinBox()
        self._menge_spin.setRange(0.01, 200.0)
        self._menge_spin.setValue(1.0)
        self._menge_spin.setSuffix(" kg/Tag")
        menge_row.addWidget(self._menge_spin)
        lo.addLayout(menge_row)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Hinzufügen")
        btn_ab = QPushButton("Abbrechen")
        btn_ok.clicked.connect(self.accept)
        btn_ab.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_ab)
        lo.addLayout(btn_row)

        self._typ_geaendert(0)

    def _typ_geaendert(self, _):
        typ = self._typ_combo.currentData()
        self._auswahl_combo.clear()
        if typ == "heu":
            for h in self._heu_qlt:
                self._auswahl_combo.addItem(h["bezeichnung"], h["id"])
        else:
            for fm in self._alle_fm:
                self._auswahl_combo.addItem(fm["name"], fm["id"])

    def ergebnis(self) -> dict | None:
        typ = self._typ_combo.currentData()
        source_id = self._auswahl_combo.currentData()
        if not source_id:
            return None
        base = {"quell_typ": typ, "menge_kg": self._menge_spin.value()}
        if typ == "heu":
            bezeichnung = self._auswahl_combo.currentText()
            base["heu_qualitaet_id"] = source_id
            base["_heu_bezeichnung"] = bezeichnung
        else:
            name = self._auswahl_combo.currentText()
            base["futtermittel_id"] = source_id
            base["_fm_name"] = name
        return base


class _AddSupplementDialog(QDialog):
    """Mini-Dialog zum Hinzufügen eines Supplements."""

    def __init__(self, alle_supps: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Supplement hinzufügen")
        self.resize(420, 180)

        lo = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Supplement:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(280)
        for s in alle_supps:
            self._combo.addItem(f"{s['name']}  [{s['typ']}]", s)
        row1.addWidget(self._combo)
        lo.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Tagesdosis (g):"))
        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.001, 9999.0)
        self._spin.setDecimals(3)
        self._spin.setValue(1.0)
        row2.addWidget(self._spin)
        lo.addLayout(row2)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color:#555; font-size:10px;")
        lo.addWidget(self._hint)

        self._combo.currentIndexChanged.connect(self._supp_geaendert)
        self._supp_geaendert(0)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Hinzufügen")
        btn_ab = QPushButton("Abbrechen")
        btn_ok.clicked.connect(self.accept)
        btn_ab.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_ab)
        lo.addLayout(btn_row)

    def _supp_geaendert(self, _):
        s = self._combo.currentData()
        if not s:
            return
        hint = s.get("hinweis") or ""
        max_d = s.get("max_tagesdosis_einheit")
        einheit = s.get("einheit", "")
        if max_d:
            konz = s.get("konzentration_je_kg", 1.0)
            max_g = max_d / konz * 1000 if konz else 9999
            self._spin.setMaximum(max_g)
            hint = f"Max. {max_d} {einheit}/Tag | " + hint
        self._hint.setText(hint[:200] if hint else "")

    def ergebnis(self) -> dict | None:
        s = self._combo.currentData()
        if not s:
            return None
        return {
            "quell_typ": "supplement",
            "supplement_id": s["id"],
            "_supp_name": s["name"],
            "menge_kg": self._spin.value() / 1000.0,
        }
