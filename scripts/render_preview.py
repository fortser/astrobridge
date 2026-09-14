"""Render the actual Qt application offscreen, without opening a desktop window."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
from PySide6.QtWidgets import QApplication
from astrobridge.config import Settings
from astrobridge.gui import Window, configure_app

app = QApplication([])
configure_app(app)
window = Window(Settings(workspace="workspace/live"))
window.show()
window.service.setCurrentIndex(window.service.findData("simbad"))
window.operation.setCurrentIndex(window.operation.findData("simbad.resolve"))
app.processEvents()
Path("docs").mkdir(exist_ok=True)
window.grab().save("docs/gui-query.png")
for result in window.bridge.history():
    if result["status"] == "success" and result["request"]["service"] == "simbad":
        window.show_result(result)
        break
app.processEvents()
window.grab().save("docs/gui-result.png")
window.close()
