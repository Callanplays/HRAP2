import sys

from PySide6.QtWidgets import QApplication

from hrap.gui.main import UnitRow
from hrap.units import LENGTH_ITEMS, compatible_units, convert, from_si, to_si


def test_convert_length_preserves_si():
    assert abs(convert(1.0, "in", "mm") - 25.4) < 1e-12
    assert abs(convert(25.4, "mm", "in") - 1.0) < 1e-12
    si = to_si(4.0, "in", "length")
    assert abs(to_si(convert(4.0, "in", "cm"), "cm", "length") - si) < 1e-12


def test_convert_temperature_affine():
    assert abs(convert(293.15, "K", "C") - 20.0) < 1e-9
    assert abs(convert(20.0, "C", "K") - 293.15) < 1e-9
    assert abs(convert(32.0, "F", "C") - 0.0) < 1e-9


def test_compatible_units():
    assert compatible_units("in", "mm")
    assert compatible_units("K", "C")
    assert not compatible_units("K", "psi")
    assert not compatible_units("%", "kg")
    assert compatible_units("kg", "g")


def test_unit_row_rewrites_number():
    app = QApplication.instance() or QApplication(sys.argv)
    _ = app
    row = UnitRow(LENGTH_ITEMS, "in", 4)
    row.spin.setValue(1.0)
    row.unit.setCurrentText("mm")
    assert abs(row.spin.value() - 25.4) < 1e-6
    row.unit.setCurrentText("in")
    assert abs(row.spin.value() - 1.0) < 1e-6


def test_set_display_does_not_convert_loaded_value():
    app = QApplication.instance() or QApplication(sys.argv)
    _ = app
    row = UnitRow(LENGTH_ITEMS, "in", 4)
    row.spin.setValue(1.0)
    row.set_display(10.0, "mm")
    assert row.unit.currentText() == "mm"
    assert abs(row.spin.value() - 10.0) < 1e-9
    # SI of the loaded 10 mm is not 1 in converted
    assert abs(to_si(row.spin.value(), "mm", "length") - 0.01) < 1e-12
    assert abs(from_si(0.01, "mm", "length") - 10.0) < 1e-12
