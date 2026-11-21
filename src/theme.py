"""Dark engineering-tool theme for the whole application."""

QSS = r"""
* {
    font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: #e6e9ee;
}

QMainWindow, QDialog, QWidget {
    background-color: #181b21;
}

QSplitter::handle {
    background-color: #10131a;
    width: 2px;
    height: 2px;
}

QMenuBar {
    background-color: #1d2128;
    border-bottom: 1px solid #2e3440;
    padding: 2px;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
}
QMenuBar::item:selected { background: #2a2f39; }
QMenuBar::item:pressed { background: #23272f; }
QMenu {
    background: #23272f;
    border: 1px solid #353b48;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 28px 8px 14px;
    border-radius: 6px;
}
QMenu::item:selected { background: #323946; }
QMenu::item:separator {
    height: 1px;
    background: #353b48;
    margin: 6px 8px;
}

/* buttons */
QPushButton {
    background: #2c313b;
    border: 1px solid #3a4150;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    color: #e6e9ee;
    min-height: 24px;
}
QPushButton:hover { background: #343a46; border-color: #485062; }
QPushButton:pressed { background: #22262e; }
QPushButton:disabled { color: #6b7280; border-color: #2a2f38; background: #23272f; }
QPushButton#primaryBtn {
    background: #ffb454;
    border: 1px solid #e07f1e;
    color: #241404;
    font-weight: 700;
}
QPushButton#primaryBtn:hover { background: #ffc069; }
QPushButton#primaryBtn:pressed { background: #e08f2b; }
QPushButton#dangerBtn {
    background: #5c2b2b;
    border-color: #7a3a3a;
    color: #ff9d8a;
}
QPushButton#dangerBtn:hover { background: #6e3232; }
QPushButton#ghostBtn {
    background: transparent;
    border: 1px solid #3a4150;
    color: #aab2c2;
}
QPushButton#ghostBtn:hover { border-color: #5a6275; color: #e6e9ee; }
QPushButton#iconBtn {
    background: transparent;
    border: 1px solid #363d4a;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 14px;
    min-width: 30px;
}
QPushButton#iconBtn:hover { background: #2e3440; }

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
    color: #aab2c2;
}
QToolButton:hover { background: #2a2f39; }
QToolButton[checked="true"] {
    background: #353d4d;
    color: #ffd28a;
    border: 1px solid #4b5568;
}

/* inputs */
QLineEdit, QTextEdit, QPlainTextEdit {
    background: #1a1e25;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 7px 9px;
    color: #e6e9ee;
    selection-background-color: #ffb454;
    selection-color: #241404;
}
QLineEdit:focus, QTextEdit:focus { border-color: #ffb454; }
QLineEdit:disabled { color: #6b7280; }

QComboBox {
    background: #1a1e25;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 24px;
}
QComboBox:hover { border-color: #4a5261; }
QComboBox:focus { border-color: #ffb454; }
QComboBox::drop-down { border: 0; width: 18px; }
QComboBox::down-arrow {
    image: none;
    border: 4px solid transparent;
    border-top: 5px solid #aab2c2;
    width: 0; height: 0;
    margin-right: 4px;
}
QComboBox QAbstractItemView {
    background: #23272f;
    border: 1px solid #353b48;
    border-radius: 8px;
    selection-background-color: #323946;
    outline: 0;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 6px 8px;
    border-radius: 5px;
}
QComboBox QLineEdit { background: transparent; border: 0; padding: 0; }

QSpinBox, QDoubleSpinBox, QScrollArea {
    background: #1a1e25;
    border: 1px solid #343a46;
    border-radius: 6px;
    padding: 4px 6px;
}
QSpinBox:focus, QDoubleSpinBox:focus { border-color: #ffb454; }

/* list containers */
QListWidget {
    background: #1f232b;
    border: 1px solid #2b313c;
    border-radius: 10px;
    padding: 6px;
    outline: 0;
}
QListWidget::item {
    padding: 9px 10px;
    border-radius: 7px;
    margin: 2px;
    border: 1px solid transparent;
}
QListWidget::item:hover { background: #262b34; }
QListWidget::item:selected {
    background: #353d4d;
    border: 1px solid #4b5568;
    color: #ffd28a;
}

QCheckBox { spacing: 6px; color: #aab2c2; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid #4a5261;
    background: #1a1e25;
}
QCheckBox::indicator:checked {
    background: #ffb454;
    border-color: #ffb454;
}
QCheckBox::indicator:checked:hover { background: #ffc069; }

QRadioButton { spacing: 6px; color: #aab2c2; }
QRadioButton::indicator {
    width: 15px; height: 15px;
    border-radius: 8px;
    border: 1px solid #4a5261;
    background: #1a1e25;
}
QRadioButton::indicator:checked { background: #ffb454; border-color: #ffb454; }

QTabWidget::pane {
    border: 1px solid #2b313c;
    border-radius: 10px;
    background: #1d2128;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #aab2c2;
    padding: 9px 16px;
    border: 1px solid transparent;
    border-bottom: 2px solid #2b313c;
    margin: 0 2px;
}
QTabBar::tab:selected { color: #ffd28a; border-bottom: 2px solid #ffb454; }
QTabBar::tab:hover { color: #e6e9ee; }

QTableWidget {
    background: #1f232b;
    border: 1px solid #2b313c;
    border-radius: 10px;
    alternate-background-color: #232833;
    gridline-color: #262b34;
    selection-background-color: #353d4d;
    outline: 0;
}
QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #262b34; }
QTableWidget::item:selected { background: #353d4d; color: #ffd28a; }
QHeaderView::section {
    background: #23272f;
    border: 0;
    border-bottom: 2px solid #2b313c;
    padding: 8px 10px;
    font-weight: 700;
    color: #9aa3b2;
    letter-spacing: 0.5px;
}
QTreeWidget {
    background: #1f232b;
    border: 1px solid #2b313c;
    border-radius: 10px;
    outline: 0;
    alternate-background-color: #232833;
}
QTreeWidget::item { padding: 6px 6px; border-radius: 5px; }
QTreeWidget::item:selected { background: #353d4d; color: #ffd28a; }
QTreeWidget::branch {
    background-color: transparent;
    border-color: #2b313c;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical { background: #3a4150; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #4a5261; }
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal { background: #3a4150; border-radius: 5px; min-width: 28px; }

QGroupBox {
    border: 1px solid #2b313c;
    border-radius: 10px;
    margin-top: 18px;
    padding: 16px 12px 12px 12px;
    color: #9aa3b2;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background: #181b21;
}

QLabel { color: #e6e9ee; }
QSlider::groove:horizontal {
    background: #2b313c;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ffb454;
    border-radius: 8px;
    width: 16px;
    height: 16px;
    margin-top: -5px;
}

QStatusBar {
    background: #14171e;
    border-top: 1px solid #262b33;
    color: #7c8594;
}
"""

PALETTE = {
    'background': '#181b21',
    'panel': '#1d2128',
    'elevated': '#2a2f38',
    'border': '#2b313c',
    'text': '#e6e9ee',
    'text_dim': '#9aa3b2',
    'accent': '#ffb454',
    'accent_dim': '#8a6420',
    'raw': '#d98a4b',
    'intermediate': '#4ea3c8',
    'final': '#58bd7e',
    'process': '#a06bd8',
    'danger': '#e06060',
}
