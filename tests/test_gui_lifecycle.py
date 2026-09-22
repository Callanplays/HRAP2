import time

import pytest


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from hrap.gui.main import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.tmax.setValue(.02)
    win.show()
    yield win
    wait_for_run(win)
    win.close()
    app.processEvents()


def wait_for_run(window):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + 5
    while window._thread is not None and time.monotonic() < deadline:
        QApplication.processEvents()
        QTest.qWait(10)
    assert window._thread is None


def test_close_waits_for_worker(window):
    window._run()
    assert not window._form.isEnabled()
    assert not window._file_menu.isEnabled()
    assert not window._examples_menu.isEnabled()
    assert not window.close()
    assert window.isVisible()
    wait_for_run(window)
    assert not window.isVisible()
    assert window._worker is None


def test_editing_inputs_invalidates_completed_results(window):
    window._run()
    wait_for_run(window)
    assert window._output is not None
    assert window._form.isEnabled()
    assert window._result_cfg["mtr_nm"] == window._settings.mtr_nm
    window.grn_L.spin.setValue(window.grn_L.spin.value() + 1)
    assert window._output is None
    assert window._result_cfg is None
    assert not window.summary.toPlainText()


def test_missing_coolprop_reports_error_and_reenables_run(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    def unavailable(*args):
        raise ImportError("CoolProp missing")

    messages = []
    monkeypatch.setattr("hrap.advanced.fluid.coolprop_sat", unavailable)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(args[-1]))
    window.adv_on.setChecked(True)
    window.ox_fluid.setCurrentText("NitrousOxide (CoolProp)")
    window._run()
    wait_for_run(window)
    assert window.run_btn.isEnabled()
    assert window._output is None
    assert len(messages) == 1 and "CoolProp missing" in messages[0]


def test_loading_restores_manufacturer(window):
    from hrap.io.config import default_cfg

    cfg = default_cfg()
    cfg["mfg"] = "Saved manufacturer"
    window.mfg.setText("Previous manufacturer")
    window._cfg_to_form(cfg)
    assert window._form_to_cfg()["mfg"] == "Saved manufacturer"
