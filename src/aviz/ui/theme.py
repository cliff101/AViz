"""Dark premium theme."""

BG_DARK = "#0a0a0f"
BG_PANEL = "#12121a"
BG_ELEVATED = "#1a1a26"
ACCENT = "#00d4ff"
ACCENT_DIM = "#0099bb"
TEXT = "#e8e8f0"
TEXT_MUTED = "#8888a0"
BORDER = "#2a2a3a"
DANGER = "#ff4466"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
QPushButton {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {ACCENT_DIM};
    background-color: #222233;
}}
QPushButton:pressed {{
    background-color: {ACCENT_DIM};
}}
QPushButton#accent {{
    background-color: {ACCENT_DIM};
    border-color: {ACCENT};
    color: #000;
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT};
}}
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {ACCENT_DIM};
    color: #fff;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
}}
QComboBox::drop-down {{
    border: none;
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {BG_ELEVATED};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    margin: -4px 0;
    background: {ACCENT};
    border-radius: 7px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG_DARK};
}}
QTabBar::tab {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{
    background: {BG_ELEVATED};
    border-bottom-color: {BG_DARK};
    color: {ACCENT};
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 600;
}}
QLabel#muted {{
    color: {TEXT_MUTED};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    background: {BG_PANEL};
}}
QProgressBar::chunk {{
    background: {ACCENT_DIM};
    border-radius: 3px;
}}
"""
