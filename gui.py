"""
PySide6 Desktop Application for LANDrop.
Refined, perfectly scaled Windows 11 Dark theme control panel.
Features High-DPI support, scrollable responsive cards, no-wrap buttons,
and clean visual alignment.
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

# Enable High DPI scaling before importing Qt GUI
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from werkzeug.serving import WSGIRequestHandler, make_server

# Prevent hanging connections from blocking server threads
WSGIRequestHandler.timeout = 15

from core.autostart import is_autostart_enabled, set_autostart
from core.config import config
from core.network import (
    find_available_port,
    generate_qr_png_bytes,
    get_connection_urls,
    get_hostname,
    get_local_ip,
)
from core.server import LandropServer
from core.version import APP_VERSION, RELEASES_URL, check_for_updates


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base_dir = Path(__file__).resolve().parent
    return base_dir / relative_path


class ServerThread(threading.Thread):
    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = make_server(self.host, self.port, app, threaded=True)

    def run(self):
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")

    def shutdown(self):
        if self.server:
            self.server.shutdown()


class ActivityBridge(QObject):
    """Bridge for thread-safe UI updates from Flask server to Qt."""
    new_activity = Signal(str, str)
    update_checked = Signal(dict)


class QRDialog(QDialog):
    """Clean, properly scaled dialog showing QR code for mobile scanning."""
    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LANDrop - Connection QR Code")
        self.setFixedSize(340, 440)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f19;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
            }
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #38bdf8;
            }
        """)

        if isinstance(urls, dict):
            self.primary_url = urls.get("primary_url", "")
            self.landrop_url = urls.get("landrop_url", "")
        else:
            self.primary_url = str(urls)
            self.landrop_url = str(urls)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        info_lbl = QLabel("Scan with your phone camera to connect:")
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        layout.addWidget(info_lbl)

        # Toggle row: Direct IP vs Permanent mDNS
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        self.btn_mode_direct = QPushButton("Direct IP (Phone)")
        self.btn_mode_direct.setStyleSheet("background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8;")
        self.btn_mode_mdns = QPushButton("Permanent (landrop.local)")

        self.btn_mode_direct.clicked.connect(self._select_direct)
        self.btn_mode_mdns.clicked.connect(self._select_mdns)

        mode_layout.addWidget(self.btn_mode_direct)
        mode_layout.addWidget(self.btn_mode_mdns)
        layout.addLayout(mode_layout)

        self.url_box = QLabel(self.primary_url)
        self.url_box.setAlignment(Qt.AlignCenter)
        self.url_box.setStyleSheet("""
            background-color: #131d31;
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
            font-weight: bold;
            color: #38bdf8;
        """)
        self.url_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.url_box)

        self.img_container = QLabel()
        self.img_container.setAlignment(Qt.AlignCenter)
        self.img_container.setStyleSheet("background-color: #ffffff; border-radius: 10px; padding: 10px;")
        layout.addWidget(self.img_container)

        self._update_qr(self.primary_url)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy URL")
        btn_copy.clicked.connect(self._copy_current)
        btn_row.addWidget(btn_copy)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _select_direct(self):
        self.btn_mode_direct.setStyleSheet("background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8;")
        self.btn_mode_mdns.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12);")
        self.url_box.setText(self.primary_url)
        self._update_qr(self.primary_url)

    def _select_mdns(self):
        self.btn_mode_mdns.setStyleSheet("background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8;")
        self.btn_mode_direct.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.12);")
        self.url_box.setText(self.landrop_url)
        self._update_qr(self.landrop_url)

    def _update_qr(self, url: str):
        qr_bytes = generate_qr_png_bytes(url)
        pix = QPixmap()
        if qr_bytes:
            pix.loadFromData(qr_bytes)
        self.img_container.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _copy_current(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.url_box.text())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LANDrop - Local Wi-Fi File Sharing & Explorer")
        self.resize(860, 740)
        self.setMinimumSize(780, 620)

        # Apply clean, properly-scaled dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget#contentWidget {
                background-color: #080c14;
            }
            QWidget {
                color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
                background: transparent;
            }
            QFrame.card {
                background-color: #0f172a;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QLabel {
                background-color: transparent;
                background: transparent;
            }
            QLabel.card-title {
                background-color: transparent;
                background: transparent;
                font-size: 13px;
                font-weight: 700;
                color: #38bdf8;
            }
            QLabel.card-subtitle {
                background-color: transparent;
                background: transparent;
                font-size: 11px;
                color: #94a3b8;
                line-height: 1.3;
            }
            QLineEdit {
                background-color: #131d31;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 7px;
                color: #f8fafc;
                padding: 7px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: #1a263d;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 7px;
                color: #f8fafc;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
                white-space: nowrap;
            }
            QPushButton:hover {
                background-color: #243452;
                border-color: #38bdf8;
                color: #ffffff;
            }
            QPushButton#primaryBtn {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
            }
            QPushButton#primaryBtn:hover {
                background-color: #0369a1;
            }
            QPushButton#dangerBtn {
                background-color: rgba(239, 68, 68, 0.12);
                border: 1px solid rgba(239, 68, 68, 0.25);
                color: #fca5a5;
            }
            QPushButton#dangerBtn:hover {
                background-color: rgba(239, 68, 68, 0.25);
                border-color: #ef4444;
                color: #ffffff;
            }
            QTableWidget {
                background-color: #131d31;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 7px;
                gridline-color: rgba(255, 255, 255, 0.03);
                selection-background-color: rgba(56, 189, 248, 0.2);
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #18233a;
                color: #94a3b8;
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                padding: 7px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QCheckBox {
                color: #f8fafc;
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.25);
                background-color: #131d31;
            }
            QCheckBox::indicator:checked {
                background-color: #10b981;
                border-color: #10b981;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # Setup icon
        self.icon_path = get_resource_path("assets/icon.ico")
        if not self.icon_path.exists():
            self.icon_path = get_resource_path("assets/icon.png")
        if self.icon_path.exists():
            self.setWindowIcon(QIcon(str(self.icon_path)))

        # Setup activity bridge
        self.bridge = ActivityBridge()
        self.bridge.new_activity.connect(self._append_log)
        self.bridge.update_checked.connect(self._on_update_checked)

        # Server setup
        self.server_thread = None
        self.server_instance = None
        self.port = config.data.get("port", 5000)

        self._build_ui()
        self._setup_tray()
        self.start_server()

    def _build_ui(self):
        # Scroll area container to guarantee responsive scaling on any display DPI
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        self.setCentralWidget(scroll_area)

        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        scroll_area.setWidget(content_widget)

        root_layout = QVBoxLayout(content_widget)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # ==========================================
        # 0. Modern Top Header Bar (No in-window menu)
        # ==========================================
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(10)

        if self.icon_path.exists():
            icon_lbl = QLabel()
            icon_pix = QPixmap(str(self.icon_path)).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_lbl.setPixmap(icon_pix)
            header_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        app_title = QLabel("LANDrop")
        app_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;")
        title_col.addWidget(app_title)

        app_desc = QLabel("High-Speed Local Wi-Fi File Sharing & Safe List Explorer")
        app_desc.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        title_col.addWidget(app_desc)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        self.btn_update = QPushButton(f"v{APP_VERSION}")
        self.btn_update.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #38bdf8;
            font-weight: 700;
            border-radius: 14px;
            padding: 5px 12px;
            font-size: 11px;
        """)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setToolTip("Click to check for latest updates")
        self.btn_update.clicked.connect(lambda: self._check_updates_async(manual=True))
        header_layout.addWidget(self.btn_update)

        self.status_badge = QLabel("● Online on Wi-Fi")
        self.status_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #34d399;
            padding: 5px 12px;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_layout.addWidget(self.status_badge)

        btn_header_web = QPushButton("Open Web App")
        btn_header_web.setObjectName("primaryBtn")
        btn_header_web.setMinimumWidth(115)
        btn_header_web.clicked.connect(self._open_browser)
        header_layout.addWidget(btn_header_web)

        root_layout.addLayout(header_layout)

        # ==========================================
        # 1. Connection Card (Hero)
        # ==========================================
        conn_card = QFrame()
        conn_card.setProperty("class", "card")
        conn_layout = QVBoxLayout(conn_card)
        conn_layout.setContentsMargins(18, 16, 18, 16)
        conn_layout.setSpacing(8)

        card_title_row = QHBoxLayout()
        card_title = QLabel("📡 Connection Address")
        card_title.setProperty("class", "card-title")
        card_title_row.addWidget(card_title)

        perm_badge = QLabel("Direct IP & mDNS")
        perm_badge.setStyleSheet("background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 8px;")
        card_title_row.addWidget(perm_badge)
        card_title_row.addStretch()
        conn_layout.addLayout(card_title_row)

        card_subtitle = QLabel("Scan the QR code or open the link below on your phone to transfer files immediately:")
        card_subtitle.setProperty("class", "card-subtitle")
        conn_layout.addWidget(card_subtitle)

        # Input + Buttons in a clean, non-wrapping row
        addr_row = QHBoxLayout()
        addr_row.setSpacing(8)

        self.url_label = QLineEdit("http://127.0.0.1:5000")
        self.url_label.setReadOnly(True)
        self.url_label.setStyleSheet("""
            background-color: #131d31;
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 7px;
            color: #38bdf8;
            font-size: 14px;
            font-weight: bold;
            font-family: 'Consolas', 'Courier New', monospace;
            padding: 7px 10px;
        """)
        addr_row.addWidget(self.url_label, 1)

        self.btn_copy_url = QPushButton("Copy Link")
        self.btn_copy_url.setMinimumWidth(85)
        self.btn_copy_url.clicked.connect(self._copy_url)
        addr_row.addWidget(self.btn_copy_url)

        self.btn_open_browser = QPushButton("Open in Browser")
        self.btn_open_browser.setObjectName("primaryBtn")
        self.btn_open_browser.setMinimumWidth(125)
        self.btn_open_browser.clicked.connect(self._open_browser)
        addr_row.addWidget(self.btn_open_browser)

        self.btn_show_qr = QPushButton("Show QR")
        self.btn_show_qr.setMinimumWidth(75)
        self.btn_show_qr.clicked.connect(self._show_qr)
        addr_row.addWidget(self.btn_show_qr)

        conn_layout.addLayout(addr_row)

        self.ip_subtext = QLabel()
        self.ip_subtext.setStyleSheet("color: #64748b; font-size: 11px; margin-top: 2px;")
        conn_layout.addWidget(self.ip_subtext)

        root_layout.addWidget(conn_card)

        # ==========================================
        # 2. Auto-Save Settings Card
        # ==========================================
        autosave_card = QFrame()
        autosave_card.setProperty("class", "card")
        autosave_layout = QVBoxLayout(autosave_card)
        autosave_layout.setContentsMargins(18, 16, 18, 16)
        autosave_layout.setSpacing(10)

        autosave_title = QLabel("📥 Auto-Save & App Settings")
        autosave_title.setProperty("class", "card-title")
        autosave_layout.addWidget(autosave_title)

        options_row = QHBoxLayout()
        options_row.setSpacing(24)

        self.chk_autosave = QCheckBox("Auto-Save incoming files without prompts")
        self.chk_autosave.setChecked(config.auto_save_enabled)
        self.chk_autosave.toggled.connect(self._toggle_autosave)
        options_row.addWidget(self.chk_autosave)

        self.chk_autostart = QCheckBox("Start with Windows on system boot (silent in tray)")
        self.chk_autostart.setChecked(is_autostart_enabled())
        self.chk_autostart.toggled.connect(self._toggle_autostart)
        options_row.addWidget(self.chk_autostart)

        options_row.addStretch()
        autosave_layout.addLayout(options_row)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        dir_lbl = QLabel("Save Folder:")
        dir_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        dir_row.addWidget(dir_lbl)

        self.txt_save_dir = QLineEdit(config.save_directory)
        self.txt_save_dir.setReadOnly(True)
        dir_row.addWidget(self.txt_save_dir, 1)

        btn_change_dir = QPushButton("Change Folder")
        btn_change_dir.setMinimumWidth(110)
        btn_change_dir.clicked.connect(self._choose_save_directory)
        dir_row.addWidget(btn_change_dir)

        btn_open_dir = QPushButton("Open in Explorer")
        btn_open_dir.setMinimumWidth(115)
        btn_open_dir.clicked.connect(self._open_save_folder)
        dir_row.addWidget(btn_open_dir)

        autosave_layout.addLayout(dir_row)

        fw_row = QHBoxLayout()
        fw_row.setSpacing(10)

        fw_lbl = QLabel("🛡️ Windows Firewall:")
        fw_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        fw_row.addWidget(fw_lbl)

        fw_desc = QLabel("Fix repeated 'Allow Python to connect' network pop-ups on this PC")
        fw_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        fw_row.addWidget(fw_desc, 1)

        btn_firewall = QPushButton("Allow in Windows Firewall (1-Click)")
        btn_firewall.setMinimumWidth(210)
        btn_firewall.clicked.connect(self._configure_firewall)
        fw_row.addWidget(btn_firewall)

        autosave_layout.addLayout(fw_row)
        root_layout.addWidget(autosave_card)

        # ==========================================
        # 3. Safe List (Shared PC Folders) Card
        # ==========================================
        safelist_card = QFrame()
        safelist_card.setProperty("class", "card")
        safelist_layout = QVBoxLayout(safelist_card)
        safelist_layout.setContentsMargins(18, 16, 18, 16)
        safelist_layout.setSpacing(8)

        safelist_title = QLabel("🔒 Safe List Folders (Shared with Wi-Fi)")
        safelist_title.setProperty("class", "card-title")
        safelist_layout.addWidget(safelist_title)

        safelist_sub = QLabel("Only folders explicitly added here can be browsed by devices on your Wi-Fi network:")
        safelist_sub.setProperty("class", "card-subtitle")
        safelist_layout.addWidget(safelist_sub)

        self.safe_table = QTableWidget(0, 2)
        self.safe_table.setHorizontalHeaderLabels(["Shared Folder Name", "Path on Computer"])
        self.safe_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.safe_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.safe_table.horizontalHeader().resizeSection(0, 220)
        self.safe_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.safe_table.setSelectionMode(QTableWidget.SingleSelection)
        self.safe_table.setMinimumHeight(130)
        safelist_layout.addWidget(self.safe_table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_add_safe = QPushButton("+ Add Folder to Safe List")
        btn_add_safe.setObjectName("primaryBtn")
        btn_add_safe.setMinimumWidth(165)
        btn_add_safe.clicked.connect(self._add_safe_folder)
        btn_row.addWidget(btn_add_safe)

        btn_remove_safe = QPushButton("Remove Selected Folder")
        btn_remove_safe.setObjectName("dangerBtn")
        btn_remove_safe.setMinimumWidth(160)
        btn_remove_safe.clicked.connect(self._remove_safe_folder)
        btn_row.addWidget(btn_remove_safe)

        btn_row.addStretch()
        safelist_layout.addLayout(btn_row)

        root_layout.addWidget(safelist_card)

        # ==========================================
        # 4. Live Activity Console Card
        # ==========================================
        log_card = QFrame()
        log_card.setProperty("class", "card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 14, 18, 14)
        log_layout.setSpacing(8)

        log_top = QHBoxLayout()
        log_title = QLabel("⚡ Live Activity Log")
        log_title.setProperty("class", "card-title")
        log_top.addWidget(log_title)
        log_top.addStretch()

        btn_clear_log = QPushButton("Clear")
        btn_clear_log.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        btn_clear_log.clicked.connect(lambda: self.log_view.clear())
        log_top.addWidget(btn_clear_log)
        log_layout.addLayout(log_top)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(100)
        self.log_view.setStyleSheet("""
            background-color: #0b1120;
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 7px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            padding: 8px 10px;
        """)
        log_layout.addWidget(self.log_view)

        root_layout.addWidget(log_card)

        self._refresh_safe_table()

    def _setup_tray(self):
        """Sets up the Windows system tray icon with custom app icon."""
        self.tray_icon = QSystemTrayIcon(self)
        if self.icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(self.icon_path)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        tray_menu = QMenu(self)
        show_action = QAction("Open LANDrop Control Panel", self)
        show_action.triggered.connect(self.showNormal)
        open_web_action = QAction("Open Web App in Browser", self)
        open_web_action.triggered.connect(self._open_browser)
        update_action = QAction(f"Check for Updates (v{APP_VERSION})...", self)
        update_action.triggered.connect(lambda: self._check_updates_async(manual=True))
        quit_action = QAction("Exit LANDrop", self)
        quit_action.triggered.connect(self._clean_exit)

        tray_menu.addAction(show_action)
        tray_menu.addAction(open_web_action)
        tray_menu.addAction(update_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def start_server(self):
        try:
            actual_port = find_available_port(self.port)
            self.port = actual_port
            self.server_instance = LandropServer(port=actual_port)

            # Register activity callback
            self.server_instance.add_activity_callback(
                lambda msg, etype: self.bridge.new_activity.emit(msg, etype)
            )

            self.server_thread = ServerThread(self.server_instance.app, "0.0.0.0", actual_port)
            self.server_thread.start()

            urls = get_connection_urls(actual_port)
            self.active_urls = urls
            self.active_landrop_url = urls["landrop_url"]
            self.active_primary_url = urls["primary_url"]
            self.active_mdns_url = urls["mdns_url"]

            # Prioritize Direct IP for reliable phone connection
            self.url_label.setText(urls["primary_url"])
            self.ip_subtext.setText(f"Direct IP: {urls['primary_url']}  •  Permanent: {urls['landrop_url']}  •  Hostname: {urls['mdns_url']}")
            self._append_log(f"Server started on port {actual_port}. Direct IP: {urls['primary_url']}.", "info")

            # Check for updates in background
            self._check_updates_async(manual=False)
        except Exception as e:
            QMessageBox.critical(self, "Server Error", f"Failed to start server: {e}")

    def _configure_firewall(self):
        """Allows LANDrop through Windows Firewall with a single click."""
        bat_path = get_resource_path("allow_firewall.bat")
        if bat_path.exists():
            cmd = f'powershell -Command "Start-Process cmd -ArgumentList \'/c \"\"{bat_path}\"\"\' -Verb RunAs"'
            os.system(cmd)
            self._append_log("Invoked Windows Firewall auto-configuration script with Administrator privileges.", "info")
            QMessageBox.information(
                self,
                "Windows Firewall Configuration",
                "A Windows User Account Control (UAC) prompt will appear.\n\n"
                "Click 'Yes' to add permanent inbound firewall rules for Port 5000 & mDNS.\n"
                "Once allowed, Windows will never prompt you again!",
            )
        else:
            ps_cmd = (
                'powershell -Command "Start-Process powershell -ArgumentList \'-Command '
                '\\\"New-NetFirewallRule -DisplayName \\\'LANDrop Wi-Fi File Transfer\\\' -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow; '
                'New-NetFirewallRule -DisplayName \\\'LANDrop Wi-Fi File Transfer UDP\\\' -Direction Inbound -LocalPort 5000 -Protocol UDP -Action Allow; '
                'New-NetFirewallRule -DisplayName \\\'LANDrop mDNS Discovery\\\' -Direction Inbound -LocalPort 5353 -Protocol UDP -Action Allow\\\"\' -Verb RunAs"'
            )
            os.system(ps_cmd)
            QMessageBox.information(
                self,
                "Windows Firewall",
                "Firewall configuration commands have been sent. Confirm the administrator prompt to apply.",
            )

    def _check_updates_async(self, manual: bool = False):
        self.manual_update_check = manual
        t = threading.Thread(target=self._run_update_check, daemon=True)
        t.start()

    def _run_update_check(self):
        res = check_for_updates()
        self.bridge.update_checked.emit(res)

    def _on_update_checked(self, res: dict):
        if res.get("update_available"):
            latest = res.get("latest_version")
            self.btn_update.setText(f"🚀 Update v{latest} Available")
            self.btn_update.setStyleSheet("""
                background-color: #f59e0b;
                color: #0b0f19;
                font-weight: 800;
                border-radius: 14px;
                padding: 5px 12px;
                font-size: 11px;
                border: 1px solid #fbbf24;
            """)
            self.btn_update.setToolTip(f"New update v{latest} available! Click to download on GitHub.")
            try:
                self.btn_update.clicked.disconnect()
            except Exception:
                pass
            self.btn_update.clicked.connect(lambda: webbrowser.open(res.get("release_url", RELEASES_URL)))

            if getattr(self, "manual_update_check", False):
                reply = QMessageBox.question(
                    self,
                    "Update Available",
                    f"A new version of LANDrop is available: v{latest}!\n\nWould you like to open the GitHub release page to download it?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    webbrowser.open(res.get("release_url", RELEASES_URL))
        else:
            self.btn_update.setText(f"✓ v{APP_VERSION} Latest")
            self.btn_update.setStyleSheet("""
                background-color: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.3);
                color: #38bdf8;
                font-weight: 700;
                border-radius: 14px;
                padding: 5px 12px;
                font-size: 11px;
            """)
            self.btn_update.setToolTip(f"You are running the latest version (v{APP_VERSION}). Click to re-check.")
            if getattr(self, "manual_update_check", False):
                QMessageBox.information(
                    self,
                    "LANDrop Up to Date",
                    f"You are currently using the latest release: v{APP_VERSION}.",
                )

    def _copy_url(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.url_label.text())
        self._append_log(f"Copied URL {self.url_label.text()} to clipboard.", "info")

    def _open_browser(self):
        webbrowser.open(self.url_label.text())

    def _show_qr(self):
        urls = getattr(self, "active_urls", self.url_label.text())
        dlg = QRDialog(urls, self)
        dlg.exec()

    def _toggle_autosave(self, checked: bool):
        config.set_auto_save(checked)
        state_str = "ENABLED" if checked else "DISABLED"
        self._append_log(f"Auto-Save setting updated: {state_str}", "info")

    def _toggle_autostart(self, checked: bool):
        success = set_autostart(checked)
        if success:
            state_str = "ENABLED" if checked else "DISABLED"
            self._append_log(f"Windows startup autostart: {state_str}", "info")
        else:
            self.chk_autostart.setChecked(not checked)
            QMessageBox.warning(self, "Startup Error", "Could not update Windows startup registry.")

    def _choose_save_directory(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Auto-Save Folder", config.save_directory)
        if new_dir:
            config.set_save_directory(new_dir)
            self.txt_save_dir.setText(new_dir)
            self._append_log(f"Auto-Save directory set to: {new_dir}", "info")

    def _open_save_folder(self):
        save_dir = config.save_directory
        if os.path.exists(save_dir):
            os.startfile(save_dir)
        else:
            QMessageBox.warning(self, "Folder Not Found", f"Directory does not exist: {save_dir}")

    def _refresh_safe_table(self):
        folders = config.get_safe_folders()
        self.safe_table.setRowCount(len(folders))
        for row, folder in enumerate(folders):
            name_item = QTableWidgetItem(f"📁  {folder.get('name', 'Unnamed')}")
            path_item = QTableWidgetItem(folder.get("path", ""))
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            path_item.setFlags(path_item.flags() ^ Qt.ItemIsEditable)
            self.safe_table.setItem(row, 0, name_item)
            self.safe_table.setItem(row, 1, path_item)

    def _add_safe_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Add to Safe List")
        if folder_path:
            try:
                entry = config.add_safe_folder(folder_path)
                self._refresh_safe_table()
                self._append_log(f"Added '{entry['name']}' to Safe List.", "info")
            except Exception as e:
                QMessageBox.warning(self, "Add Folder Error", str(e))

    def _remove_safe_folder(self):
        current_row = self.safe_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Selection Required", "Please select a folder from the table to remove.")
            return

        folders = config.get_safe_folders()
        if 0 <= current_row < len(folders):
            folder = folders[current_row]
            confirm = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Remove '{folder['name']}' from the Safe List?\n(No files on your computer will be deleted).",
            )
            if confirm == QMessageBox.Yes:
                config.remove_safe_folder(folder["id"])
                self._refresh_safe_table()
                self._append_log(f"Removed '{folder['name']}' from Safe List.", "info")

    def _clean_exit(self):
        if self.server_instance:
            self.server_instance.shutdown()
        if self.server_thread:
            self.server_thread.shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        # Clean shutdown when user closes the window
        if self.server_instance:
            self.server_instance.shutdown()
        if self.server_thread:
            self.server_thread.shutdown()
        event.accept()


def run_gui(start_minimized: bool = False):
    app = QApplication(sys.argv)
    app.setApplicationName("LANDrop")
    window = MainWindow()
    if not start_minimized:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
