"""Throat × injector Cd sweep window."""
from __future__ import annotations

import traceback

import numpy as np
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hrap.engine.sweep import SweepCase, sweep
from hrap.units import DisplayUnits, from_si, to_si

OVER_LIMIT = QColor(200, 60, 60, 150)
HIGH_DP = QColor(215, 160, 40, 150)

METRICS = [
    ("Peak chamber pressure", "peak_P_cmbr", "pressure"),
    ("Average injector ΔP", "avg_inj_dP", "pressure"),
    ("Total impulse", "total_impulse", "impulse"),
    ("Peak thrust", "peak_thrust", "force"),
    ("Burn time", "burn_time", None),
]


class SweepWorker(QObject):
    case_done = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, cfg: dict, throats: list[float], cds: list[float]):
        super().__init__()
        self.cfg, self.throats, self.cds = cfg, throats, cds
        self.stop = False

    def run(self):
        try:
            for case in sweep(self.cfg, self.throats, self.cds):
                self.case_done.emit(case)
                if self.stop:
                    break
        except Exception:
            self.failed.emit(traceback.format_exc())
        self.finished.emit()


class SweepDialog(QDialog):
    def __init__(self, cfg: dict, units: DisplayUnits, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Throat / injector Cd sweep")
        self.resize(900, 560)
        self.cfg, self.units = cfg, units
        self.cases: list[SweepCase] = []
        self._thread: QThread | None = None
        self._worker: SweepWorker | None = None

        length, pressure = units.length, units.pressure
        throat = from_si(to_si(cfg["noz_thrt"], cfg["noz_thrt_unit"], "length"), length, "length")
        cd = float(cfg["inj_Cd"])
        self.throat_lo, self.throat_hi = self._spin(0.7 * throat, 4), self._spin(1.3 * throat, 4)
        self.throat_n = self._count(7)
        self.cd_lo, self.cd_hi = self._spin(0.5 * cd, 3), self._spin(min(1.0, 1.5 * cd), 3)
        self.cd_n = self._count(6)
        self.max_chamber = self._spin(from_si(to_si(500.0, "psi", "pressure"), pressure, "pressure"), 1)
        self.max_dp = self._spin(from_si(to_si(300.0, "psi", "pressure"), pressure, "pressure"), 1)
        self.shown = QComboBox()
        self.shown.addItems([m[0] for m in METRICS])
        self.shown.currentIndexChanged.connect(self._fill_table)
        self.max_chamber.valueChanged.connect(self._fill_table)
        self.max_dp.valueChanged.connect(self._fill_table)

        form = QFormLayout()
        form.addRow(f"Throat diameter ({length})", self._range_row(self.throat_lo, self.throat_hi, self.throat_n))
        form.addRow("Injector Cd", self._range_row(self.cd_lo, self.cd_hi, self.cd_n))
        form.addRow(f"Chamber pressure limit ({pressure}, absolute)", self.max_chamber)
        form.addRow(f"Average injector ΔP warning ({pressure})", self.max_dp)
        form.addRow("Show", self.shown)

        self.run_btn = QPushButton("Run sweep")
        self.run_btn.clicked.connect(self._run)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.export_btn = QPushButton("Export CSV…")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        self.progress = QProgressBar()
        buttons = QHBoxLayout()
        for w in (self.run_btn, self.stop_btn, self.export_btn):
            buttons.addWidget(w)
        buttons.addWidget(self.progress, 1)

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        legend = QLabel(
            "Rows are throat diameters, columns are injector Cds. Red: peak chamber pressure over the limit. "
            "Yellow: average injector ΔP over the warning, where HRAP's liquid-only (SPI) injector model overpredicts "
            "oxidizer flow. Hover a cell for every result."
        )
        legend.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        layout.addWidget(legend)

    @staticmethod
    def _spin(value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0.0, 1e6)
        spin.setValue(value)
        return spin

    @staticmethod
    def _count(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 50)
        spin.setValue(value)
        return spin

    @staticmethod
    def _range_row(lo: QDoubleSpinBox, hi: QDoubleSpinBox, n: QSpinBox) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        for label, w in (("from", lo), ("to", hi), ("steps", n)):
            h.addWidget(QLabel(label))
            h.addWidget(w, 1)
        return row

    def _axes(self) -> tuple[list[float], list[float]]:
        throats = np.linspace(self.throat_lo.value(), self.throat_hi.value(), self.throat_n.value())
        cds = np.linspace(self.cd_lo.value(), self.cd_hi.value(), self.cd_n.value())
        return [to_si(t, self.units.length, "length") for t in throats], [float(c) for c in cds]

    def _run(self):
        throats, cds = self._axes()
        self._grid = (throats, cds)
        self.cases = []
        self.table.clear()
        self.table.setRowCount(len(throats))
        self.table.setColumnCount(len(cds))
        self.table.setVerticalHeaderLabels([f"{from_si(t, self.units.length, 'length'):.4g} {self.units.length}" for t in throats])
        self.table.setHorizontalHeaderLabels([f"Cd {c:.3g}" for c in cds])
        self.progress.setRange(0, len(throats) * len(cds))
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = SweepWorker(self.cfg, throats, cds)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.case_done.connect(self._on_case)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _stop(self):
        if self._worker is not None:
            self._worker.stop = True
        self.stop_btn.setEnabled(False)

    def _on_case(self, case: SweepCase):
        self.cases.append(case)
        self.progress.setValue(len(self.cases))
        self._fill_cell(len(self.cases) - 1, case)

    def _on_failed(self, text: str):
        self.progress.setFormat("Sweep failed")
        self.table.setToolTip(text)

    def _on_thread_finished(self):
        thread = self._thread
        thread.wait()
        thread.deleteLater()
        self._thread = self._worker = None
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(bool(self.cases))

    def _fill_table(self):
        for i, case in enumerate(self.cases):
            self._fill_cell(i, case)

    def _fill_cell(self, index: int, case: SweepCase):
        u = self.units
        ncols = self.table.columnCount()
        _label, field, quantity = METRICS[self.shown.currentIndex()]
        value = getattr(case, field)
        item = QTableWidgetItem(u.text(value, quantity) if quantity else f"{value:.3g} s")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        limit = to_si(self.max_chamber.value(), u.pressure, "pressure")
        dp_limit = to_si(self.max_dp.value(), u.pressure, "pressure")
        if case.peak_P_cmbr > limit:
            item.setBackground(OVER_LIMIT)
        elif case.avg_inj_dP > dp_limit:
            item.setBackground(HIGH_DP)
        item.setToolTip("\n".join([
            f"Throat: {u.text(case.throat, 'length')}",
            f"Injector Cd: {case.inj_Cd:.3g}",
            f"Peak chamber pressure: {u.text(case.peak_P_cmbr, 'pressure')} (absolute)",
            f"Average injector ΔP: {u.text(case.avg_inj_dP, 'pressure')}",
            f"Total impulse: {u.text(case.total_impulse, 'impulse')}",
            f"Peak thrust: {u.text(case.peak_thrust, 'force')}",
            f"Burn time: {case.burn_time:.3g} s",
            f"End: {case.end_cond}",
        ]))
        self.table.setItem(index // ncols, index % ncols, item)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export sweep", "HRAP_sweep.csv", "CSV (*.csv)")
        if not path:
            return
        u = self.units
        header = (f"throat_{u.length},inj_Cd,peak_P_cmbr_{u.pressure},avg_inj_dP_{u.pressure},"
                  f"total_impulse_{u.force}s,peak_thrust_{u.force},burn_time_s,end_cond")
        rows = [
            f"{from_si(c.throat, u.length, 'length'):.6g},{c.inj_Cd:.6g},{u.value(c.peak_P_cmbr, 'pressure'):.6g},"
            f"{u.value(c.avg_inj_dP, 'pressure'):.6g},{u.value(c.total_impulse, 'impulse'):.6g},"
            f"{u.value(c.peak_thrust, 'force'):.6g},{c.burn_time:.6g},{c.end_cond}"
            for c in self.cases
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join([header, *rows]) + "\n")

    def closeEvent(self, event):
        if self._thread is not None:
            self._stop()
            event.ignore()
            self.progress.setFormat("Stopping after the current run…")
            self._thread.finished.connect(self.close)
        else:
            event.accept()
