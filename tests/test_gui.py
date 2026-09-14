import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from astrobridge.gui import Window, configure_app


def test_gui_forms_history_and_result(bridge):
    app = QApplication.instance() or QApplication([])
    configure_app(app)
    window = Window(bridge.settings)
    window.service.setCurrentIndex(window.service.findData("simbad"))
    window.operation.setCurrentIndex(window.operation.findData("simbad.resolve"))
    assert window.form_request()["params"]["name"] == "M31"
    window.form_to_json()
    assert window.current_request()["operation"] == "simbad.resolve"
    result = bridge.run({"service": "test", "operation": "tap.query", "params": {"query": "SELECT TOP 2 * FROM sample"}})
    window.show_result(result)
    assert window.model.rowCount() == 2
    window.filter.setText("second")
    assert window.proxy.rowCount() == 1
    window.refresh_history()
    assert window.history.rowCount() == 1
    window.close()
    app.processEvents()


def test_gui_worker_finishes_without_blocking_event_loop(bridge):
    import time
    app = QApplication.instance() or QApplication([])
    window = Window(bridge.settings)
    window.set_request({"service": "test", "operation": "tap.query", "params": {"query": "SELECT TOP 2 * FROM sample"}})
    window.execute()
    assert not window.run_button.isEnabled()
    deadline = time.monotonic() + 10
    while window.worker.isRunning() and time.monotonic() < deadline:
        app.processEvents()
        window.worker.wait(10)
    app.processEvents()
    assert not window.worker.isRunning()
    assert window.manifest["status"] == "success"
    assert window.run_button.isEnabled()
    window.close()
