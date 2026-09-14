"""Qt desktop client. All network work runs off the GUI thread."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import quote, urlsplit, urlunsplit

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                              QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                              QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTableView,
                              QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView)

from .catalog import OPERATIONS, supports
from .config import Settings, load_settings
from .core import Bridge
from .errors import BridgeError
from .tables import columns
from .util import dumps, jsonable

LABELS = {"tap.query": "ADQL-запрос", "tap.cone": "Поиск вокруг координат", "tap.tables": "Найти таблицы",
          "tap.columns": "Колонки и единицы", "simbad.resolve": "Найти объект по имени", "mast.cone": "Наблюдения по координатам",
          "mast.search": "Наблюдения по фильтрам", "mast.products": "Файлы наблюдения", "horizons.query": "Эфемериды",
          "literature.search": "Поиск литературы", "download": "Скачать файл", "vo.sia": "Поиск изображений SIA", "vo.ssa": "Поиск спектров SSA"}

STYLE = """
QWidget { background: #111827; color: #e5eaf3; font-size: 13px; }
QMainWindow { background: #0b1120; }
QLabel#title { font-size: 25px; font-weight: 700; color: #66ded1; }
QLabel#subtitle { color: #9aaac3; padding-bottom: 8px; }
QPushButton { background: #25334b; border: 1px solid #3a4961; border-radius: 6px; padding: 8px 15px; }
QPushButton:hover { background: #344663; } QPushButton:disabled { color: #65728b; }
QPushButton#primary { background: #117e78; border-color: #29b9a9; font-weight: 600; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: #0b1220; border: 1px solid #34425b; border-radius: 4px; padding: 6px; selection-background-color: #185e69; }
QTabWidget::pane { border: 1px solid #34425b; }
QTabBar::tab { background: #1b2639; padding: 10px 18px; }
QTabBar::tab:selected { background: #284155; color: #7fe4d8; }
QTableView, QTableWidget { alternate-background-color: #182438; gridline-color: #28364d; selection-background-color: #215464; }
QHeaderView::section { background: #233047; padding: 7px; border: none; }
QScrollBar { background: #162137; } QToolTip { background: #25334b; color: white; }
"""


def configure_app(app):
    app.setStyle("Fusion")
    # Qt's offscreen platform on Windows may not enumerate system fonts.
    if os.name == "nt":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisb.ttf", "consola.ttf"):
            if (fonts / filename).is_file():
                QFontDatabase.addApplicationFont(str(fonts / filename))
        app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)


class TableModel(QAbstractTableModel):
    def __init__(self, table=None):
        super().__init__()
        self.table = table

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.table is None else len(self.table)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.table is None else len(self.table.colnames)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.table is None:
            return None
        value = jsonable(self.table[index.row()][index.column()])
        if role == Qt.ItemDataRole.DisplayRole:
            return "—" if value is None else str(value)
        if role == Qt.ItemDataRole.UserRole:
            return value if isinstance(value, (int, float, str)) else str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if self.table is None:
            return None
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        if orientation == Qt.Orientation.Horizontal:
            col = self.table[self.table.colnames[section]]
            if role == Qt.ItemDataRole.DisplayRole:
                return col.name + (f" [{col.unit}]" if col.unit else "")
            if role == Qt.ItemDataRole.ToolTipRole:
                return str(col.description or col.meta)
        return None


class Worker(QThread):
    progress = Signal(str)
    result = Signal(object)

    def __init__(self, bridge, request):
        super().__init__()
        self.bridge, self.request = bridge, request
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.bridge.run(self.request, self.cancel, self.progress.emit))
        except BridgeError as exc:
            self.result.emit({"status": "error", "error": exc.as_dict()})
        except Exception as exc:
            self.result.emit({"status": "error", "error": {"message": f"Ошибка {type(exc).__name__}"}})


class Window(QMainWindow):
    def __init__(self, settings=None, config_path=None):
        super().__init__()
        self.settings = settings or load_settings(config_path)
        self.config_path = config_path or os.environ.get("ASTROBRIDGE_CONFIG", "astrobridge.local.json")
        self.bridge = Bridge(self.settings)
        self.worker = None
        self.manifest = None
        self.inputs = {}
        self.setWindowTitle("AstroBridge · Astronomy Data Workspace")
        self.resize(1360, 880)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        title = QLabel("AstroBridge")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Астрономические архивы  /  воспроизводимые запросы  /  GUI + CLI")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._query_tab()
        self._results_tab()
        self._history_tab()
        self._settings_tab()
        self._help_tab()
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"Готово · {self.bridge.root}")
        self.refresh_services()
        self.refresh_history()
        copy_action = QAction("Копировать ячейки", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.copy_cells)
        self.table_view.addAction(copy_action)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

    def button(self, label, slot, primary=False):
        button = QPushButton(label)
        if primary:
            button.setObjectName("primary")
        button.clicked.connect(slot)
        return button

    def _query_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.service = QComboBox()
        self.service.setMinimumWidth(320)
        self.operation = QComboBox()
        row.addWidget(QLabel("Архив"))
        row.addWidget(self.service, 1)
        row.addWidget(QLabel("Операция"))
        row.addWidget(self.operation, 1)
        layout.addLayout(row)
        self.mode = QTabWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.form_widget = QWidget()
        self.form = QFormLayout(self.form_widget)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(self.form_widget)
        self.mode.addTab(scroll, "Форма")
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.mode.addTab(self.editor, "JSON-запрос для LLM")
        layout.addWidget(self.mode, 1)
        limits = QHBoxLayout()
        self.limit = QSpinBox()
        self.limit.setRange(1, 100000)
        self.limit.setValue(1000)
        self.cache = QCheckBox("Использовать свежий кэш")
        self.cache.setChecked(True)
        limits.addWidget(QLabel("Лимит строк / размер страницы"))
        limits.addWidget(self.limit)
        limits.addWidget(self.cache)
        limits.addStretch()
        limits.addWidget(self.button("Форма → JSON", self.form_to_json))
        layout.addLayout(limits)
        actions = QHBoxLayout()
        self.run_button = self.button("Выполнить запрос", self.execute, True)
        self.cancel_button = self.button("Отменить", self.cancel_run)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.button("Открыть запрос…", self.load_request))
        actions.addWidget(self.button("Сохранить запрос…", self.save_request))
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setMaximumBlockCount(300)
        layout.addWidget(self.log)
        self.tabs.addTab(page, "Новый запрос")
        self.service.currentIndexChanged.connect(self.refresh_operations)
        self.operation.currentIndexChanged.connect(self.refresh_form)

    def _results_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.summary = QLabel("Выполните запрос или откройте результат из истории.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Фильтр отображения по всем колонкам…")
        row.addWidget(self.filter, 1)
        row.addWidget(self.button("Экспорт всей таблицы…", self.export_result))
        row.addWidget(self.button("Скачать выбранный URL…", self.selected_download))
        layout.addLayout(row)
        split = QSplitter(Qt.Orientation.Vertical)
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.model = TableModel()
        self.proxy.setSourceModel(self.model)
        self.table_view.setModel(self.proxy)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        split.addWidget(self.table_view)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(QFont("Consolas", 10))
        split.addWidget(self.details)
        split.setSizes([500, 150])
        layout.addWidget(split)
        self.tabs.addTab(page, "Результат и происхождение")

    def _history_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(self.button("Обновить", self.refresh_history))
        row.addWidget(self.button("Открыть результат", self.open_history))
        row.addWidget(self.button("Повторить / изменить запрос", self.repeat_history))
        row.addStretch()
        layout.addLayout(row)
        self.history = QTableWidget(0, 6)
        self.history.setHorizontalHeaderLabels(["UTC", "Архив", "Операция", "Статус", "Строк", "Run ID"])
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history.doubleClicked.connect(self.open_history)
        layout.addWidget(self.history)
        self.tabs.addTab(page, "История")

    def _settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.workspace_input = QLineEdit(str(self.bridge.root))
        form.addRow("Каталог данных и истории", self.workspace_input)
        self.proxy_mode = QComboBox()
        for label, value in [("Переменные окружения", "environment"), ("Указанный прокси", "manual"), ("Прямое подключение", "direct")]:
            self.proxy_mode.addItem(label, value)
        self.proxy_mode.setCurrentIndex(self.proxy_mode.findData(self.settings.proxy_mode))
        form.addRow("Режим сети", self.proxy_mode)
        self.proxy_url = QLineEdit(self.settings.proxy_url)
        self.proxy_url.setPlaceholderText("http://127.0.0.1:8080 или socks5h://127.0.0.1:1080")
        form.addRow("URL прокси (без пароля)", self.proxy_url)
        self.proxy_env = QLineEdit(self.settings.proxy_env)
        form.addRow("Переменная с полным URL прокси", self.proxy_env)
        self.proxy_user = QLineEdit()
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Пользователь прокси (на эту сессию)", self.proxy_user)
        form.addRow("Пароль прокси (на эту сессию)", self.proxy_password)
        self.ca_input = QLineEdit(self.settings.ca_bundle)
        form.addRow("CA bundle (необязательно)", self.ca_input)
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 3600)
        self.timeout_input.setValue(int(self.settings.timeout))
        form.addRow("HTTP timeout, секунд", self.timeout_input)
        self.job_timeout_input = QSpinBox()
        self.job_timeout_input.setRange(10, 86400)
        self.job_timeout_input.setValue(int(self.settings.job_timeout))
        form.addRow("Ожидание TAP job / ответа, секунд", self.job_timeout_input)
        self.download_cap = QSpinBox()
        self.download_cap.setRange(1, 1048576)
        self.download_cap.setValue(int(self.settings.max_download_mb))
        form.addRow("Лимит одного скачивания, MiB", self.download_cap)
        layout.addLayout(form)
        info = QLabel("Авторизация прокси хранится только в памяти этого процесса. Для повторных запусков задайте переменную окружения.\nSOCKS5h передаёт разрешение имён прокси. TLS проверяется; автоматического перехода с прокси на прямое подключение нет.")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addWidget(QLabel("Дополнительные сервисы / переопределение endpoint (JSON):"))
        self.services_editor = QPlainTextEdit(dumps(self.settings.services, indent=2))
        self.services_editor.setFont(QFont("Consolas", 10))
        layout.addWidget(self.services_editor, 1)
        row = QHBoxLayout()
        self.apply_button = self.button("Применить", self.apply_settings, True)
        self.save_settings_button = self.button("Сохранить настройки…", self.save_settings)
        row.addWidget(self.apply_button)
        row.addWidget(self.save_settings_button)
        row.addStretch()
        layout.addLayout(row)
        self.tabs.addTab(page, "Сеть и сервисы")

    def _help_tab(self):
        help_text = QPlainTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText("БЫСТРЫЙ СТАРТ\n\n1. SIMBAD → Найти объект по имени → M31.\n2. Gaia → Поиск вокруг координат. Все углы в десятичных градусах, ICRS.\n3. Для неизвестного каталога: Найти таблицы → Колонки и единицы → ADQL.\n4. MAST: найдите наблюдения, скопируйте obsid, получите файлы наблюдения.\n5. Выберите dataURI / access_url в результате и нажмите «Скачать выбранный URL».\n\nJSON И CLI\n\nФорма → JSON создаёт тот же запрос, который принимает:\n  astrobridge run request.json\n\n  astrobridge schema\n  astrobridge providers\n  astrobridge resolve M31\n  astrobridge --proxy socks5h://127.0.0.1:1080 resolve M31\n\nРезультаты и исходные ответы сохраняются в workspace/runs/<run_id>.\nЭкспорт включает всю сохранённую таблицу, независимо от фильтра отображения.\nCSV не сохраняет все единицы и метаданные: для науки предпочитайте ECSV/FITS/VOTable.\n\nПолное руководство: README.md и README_LLM.md в каталоге проекта.\n\nОТМЕНА\n\nОтмена проверяется между сетевыми чтениями и этапами. Заблокированное HTTP-чтение может ждать до timeout. Для TAP async выполняется попытка ABORT; её результат записывается в remote-job.json.\n\nНАУЧНАЯ ИНТЕРПРЕТАЦИЯ\n\nУсечённая выборка не является полной. TOP без ORDER BY не задаёт воспроизводимый порядок строк. Проверяйте релиз, шкалы времени, единицы, функцию селекции и права на данные. Программа не выполняет научную интерпретацию автоматически.")
        self.tabs.addTab(help_text, "Помощь")

    def refresh_services(self):
        old = self.service.currentData() or "simbad"
        self.service.blockSignals(True)
        self.service.clear()
        for name, service in self.bridge.services.items():
            self.service.addItem(f"{service.get('label', name)}  ·  {name}", name)
        self.service.setCurrentIndex(max(0, self.service.findData(old)))
        self.service.blockSignals(False)
        self.refresh_operations()

    def refresh_operations(self):
        service = self.bridge.services.get(self.service.currentData())
        if not service:
            return
        self.operation.blockSignals(True)
        self.operation.clear()
        for name in OPERATIONS:
            if supports(service, name) and (name != "simbad.resolve" or self.service.currentData() == "simbad"):
                self.operation.addItem(LABELS.get(name, name), name)
        preferred = "simbad.resolve" if self.service.currentData() == "simbad" else "tap.cone" if self.service.currentData() == "gaia" else "tap.tables" if service["kind"] == "tap" else None
        if preferred:
            index = self.operation.findData(preferred)
            if index >= 0:
                self.operation.setCurrentIndex(index)
        self.operation.blockSignals(False)
        self.refresh_form()

    def refresh_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.inputs.clear()
        name = self.operation.currentData()
        if not name:
            return
        spec = OPERATIONS[name]
        example = dict(spec["example"])
        service = self.bridge.services[self.service.currentData()]
        if name == "tap.query" and self.service.currentData() != "gaia":
            example["query"] = "SELECT TOP 10 table_name,description FROM TAP_SCHEMA.tables"
        if name == "tap.columns":
            example["table"] = service.get("table", "TAP_SCHEMA.tables")
        for key, item in spec["properties"].items():
            value = example.get(key, item.get("default", ""))
            if item["type"] == "boolean":
                widget = QCheckBox()
                widget.setChecked(bool(value))
            elif "enum" in item:
                widget = QComboBox()
                widget.addItems(item["enum"])
                if value in item["enum"]:
                    widget.setCurrentText(value)
            elif key in {"query", "filters"}:
                widget = QPlainTextEdit(dumps(value, indent=2) if item["type"] == "array" else str(value))
                widget.setFont(QFont("Consolas", 11))
                widget.setMinimumHeight(130)
            else:
                widget = QLineEdit(str(value))
                widget.setPlaceholderText(item["description"])
            widget.setToolTip(item["description"])
            self.form.addRow(key + (" *" if key in spec["required"] else ""), widget)
            self.inputs[key] = widget
        self.editor.setPlainText(dumps({"service": self.service.currentData(), "operation": name, "params": example, "limit": self.limit.value()}, indent=2))

    def form_request(self):
        name = self.operation.currentData()
        params = {}
        for key, widget in self.inputs.items():
            item = OPERATIONS[name]["properties"][key]
            if isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
                continue
            value = widget.currentText() if isinstance(widget, QComboBox) else widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()
            if not value.strip():
                continue
            kind = item["type"]
            params[key] = json.loads(value) if kind in {"array", "object"} else int(value) if kind == "integer" else float(value) if kind == "number" else value
        return {"service": self.service.currentData(), "operation": name, "params": params, "limit": self.limit.value(), "cache": self.cache.isChecked()}

    def current_request(self):
        return self.form_request() if self.mode.currentIndex() == 0 else json.loads(self.editor.toPlainText())

    def form_to_json(self):
        try:
            self.editor.setPlainText(dumps(self.form_request(), indent=2))
            self.mode.setCurrentIndex(1)
        except (ValueError, TypeError):
            self.show_error("Проверьте числовые поля и JSON-фильтры.")

    def execute(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            request = self.bridge.validate(self.current_request())
        except (BridgeError, ValueError) as exc:
            self.show_error(str(exc) if isinstance(exc, BridgeError) else "Некорректный JSON или числовое поле.")
            return
        self.log.clear()
        self.set_busy(True)
        self.worker = Worker(self.bridge, request)
        self.worker.progress.connect(self.log.appendPlainText)
        self.worker.result.connect(self.finished_result)
        self.worker.finished.connect(lambda: self.set_busy(False))
        self.worker.start()

    def set_busy(self, busy):
        self.run_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.apply_button.setEnabled(not busy)
        self.save_settings_button.setEnabled(not busy)
        self.statusBar().showMessage("Запрос выполняется…" if busy else "Готово")

    def cancel_run(self):
        if self.worker:
            self.worker.cancel.set()
            self.log.appendPlainText("Запрошена отмена; ожидается завершение текущего сетевого чтения.")

    def finished_result(self, manifest):
        if "run_id" in manifest:
            self.show_result(manifest)
            self.refresh_history()
        else:
            self.show_error(manifest.get("error", {}).get("message", "Ошибка запроса"))

    def show_result(self, manifest):
        try:
            table = self.bridge.table(manifest["run_id"])
        except BridgeError as exc:
            self.show_error(str(exc))
            return
        self.manifest = manifest
        self.model = TableModel(table)
        self.proxy.setSourceModel(self.model)
        self.filter.clear()
        self.details.setPlainText(dumps(manifest, indent=2))
        warnings = "\n".join(manifest.get("warnings", []))
        error = manifest.get("error", {}).get("message", "")
        self.summary.setText(f"{manifest['status'].upper()}  ·  {manifest.get('row_count', 0)} строк  ·  {manifest['run_id']}"
                             + ("  ·  КЭШ" if manifest.get("cache_hit") else "") + ("  ·  УСЕЧЕНО" if manifest.get("truncated") else "")
                             + ("\n" + warnings if warnings else "") + ("\n" + error if error else ""))
        self.table_view.horizontalHeader().setDefaultSectionSize(170)
        self.tabs.setCurrentIndex(1)

    def refresh_history(self):
        self.history_items = self.bridge.history(500)
        self.history.setRowCount(len(self.history_items))
        for row, m in enumerate(self.history_items):
            values = [m["started_at"], m["request"]["service"], m["request"]["operation"], m["status"], m.get("row_count", ""), m["run_id"]]
            for col, value in enumerate(values):
                self.history.setItem(row, col, QTableWidgetItem(str(value)))

    def open_history(self, *args):
        row = self.history.currentRow()
        if row >= 0:
            self.show_result(self.history_items[row])

    def repeat_history(self):
        row = self.history.currentRow()
        if row >= 0:
            self.set_request(self.history_items[row]["request"])

    def set_request(self, request):
        index = self.service.findData(request.get("service"))
        if index >= 0:
            self.service.setCurrentIndex(index)
        index = self.operation.findData(request.get("operation"))
        if index >= 0:
            self.operation.setCurrentIndex(index)
        self.editor.setPlainText(dumps(request, indent=2))
        self.mode.setCurrentIndex(1)
        self.tabs.setCurrentIndex(0)

    def load_request(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть запрос", "", "JSON (*.json)")
        if path:
            try:
                request = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                self.bridge.validate(request)
                self.set_request(request)
            except (OSError, ValueError, BridgeError):
                self.show_error("Не удалось прочитать или проверить запрос.")

    def save_request(self):
        try:
            request = self.bridge.validate(self.current_request())
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить запрос", "request.json", "JSON (*.json)")
            if path:
                Path(path).write_text(dumps(request, indent=2), encoding="utf-8")
        except (ValueError, OSError, BridgeError):
            self.show_error("Не удалось сохранить запрос; проверьте поля и путь.")

    def export_result(self):
        if not self.manifest:
            return
        path, selected = QFileDialog.getSaveFileName(self, "Экспорт всей таблицы", "result.ecsv", "ECSV (*.ecsv);;CSV (*.csv);;FITS (*.fits);;VOTable (*.vot);;JSON (*.json)")
        if path:
            fmt = {"ECSV": "ecsv", "CSV": "csv", "FITS": "fits", "VOTable": "votable", "JSON": "json"}[selected.split(" ")[0]]
            try:
                self.bridge.export(self.manifest["run_id"], path, fmt)
                self.statusBar().showMessage(f"Сохранено: {path}")
            except Exception as exc:
                self.show_error(str(exc) if isinstance(exc, BridgeError) else "Не удалось экспортировать таблицу в выбранный формат.")

    def selected_download(self):
        index = self.table_view.currentIndex()
        value = self.proxy.data(index)
        if not isinstance(value, str) or not value.startswith(("https://", "http://", "mast:")):
            self.show_error("Выберите ячейку с access_url, dataURI или другим URL файла.")
            return
        self.set_request({"service": "mast", "operation": "download", "params": {"url": value}})

    def copy_cells(self):
        indexes = sorted(self.table_view.selectedIndexes(), key=lambda index: (index.row(), index.column()))
        rows = {}
        for index in indexes:
            rows.setdefault(index.row(), []).append(str(self.proxy.data(index) or ""))
        QApplication.clipboard().setText("\n".join("\t".join(values) for values in rows.values()))

    def apply_settings(self):
        try:
            settings = replace(self.settings, workspace=self.workspace_input.text(), proxy_mode=self.proxy_mode.currentData(),
                               proxy_url=self.proxy_url.text().strip(), proxy_env=self.proxy_env.text().strip(), ca_bundle=self.ca_input.text().strip(),
                               timeout=self.timeout_input.value(), job_timeout=self.job_timeout_input.value(), max_download_mb=self.download_cap.value(),
                               services=json.loads(self.services_editor.toPlainText()))
            settings.validate()
            bridge = Bridge(settings)
            if self.proxy_user.text() or self.proxy_password.text():
                if not settings.proxy_url:
                    raise BridgeError("config", "Для авторизации укажите URL прокси.")
                parsed = urlsplit(settings.proxy_url)
                credentials = quote(self.proxy_user.text(), safe="") + ":" + quote(self.proxy_password.text(), safe="")
                os.environ[settings.proxy_env] = urlunsplit((parsed.scheme, credentials + "@" + parsed.netloc, parsed.path, parsed.query, ""))
                self.proxy_password.clear()
                self.proxy_user.clear()
            self.settings, self.bridge = settings, bridge
            self.manifest = None
            self.model = TableModel()
            self.proxy.setSourceModel(self.model)
            self.details.clear()
            self.summary.setText("Настройки изменены. Откройте результат из истории выбранного каталога.")
            self.refresh_services()
            self.refresh_history()
            self.statusBar().showMessage("Настройки применены. Пароли в файл не записываются.")
            return True
        except (ValueError, BridgeError) as exc:
            self.show_error(str(exc) if isinstance(exc, BridgeError) else "Некорректный JSON сервисов.")
            return False

    def save_settings(self):
        if self.apply_settings():
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить настройки", self.config_path, "JSON (*.json)")
            if path:
                self.settings.save(path)
                self.config_path = path

    def show_error(self, message):
        QMessageBox.warning(self, "AstroBridge", message)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_run()
            self.statusBar().showMessage("Дождитесь отмены запроса, затем закройте окно.")
            event.ignore()
        else:
            event.accept()


def main(settings=None, config_path=None):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    configure_app(app)
    try:
        window = Window(settings, config_path)
    except (BridgeError, OSError) as exc:
        QMessageBox.critical(None, "AstroBridge — ошибка запуска", str(exc) if isinstance(exc, BridgeError) else "Не удалось открыть каталог данных или конфигурацию.")
        return 1
    window.show()
    return app.exec()
