"""Tema escuro da aplicação."""
from __future__ import annotations

BG = "#0f1218"
PANEL = "#151a23"
CARD = "#1b2130"
BORDER = "#2a3244"
TEXT = "#e6e9ef"
MUTED = "#8b93a7"
ACCENT = "#4f8cff"
GREEN = "#3ecf8e"
YELLOW = "#f5b945"
RED = "#f0616d"
PURPLE = "#a78bfa"
CYAN = "#38bdf8"
PALETTE = [ACCENT, GREEN, YELLOW, RED, PURPLE, CYAN, "#fb923c", "#f472b6"]

STATUS_COLORS = {
    # contas
    "active": GREEN, "paused": YELLOW, "tracking": CYAN, "done": ACCENT, "error": RED, "archived": MUTED,
    # tarefas
    "pending": YELLOW, "running": CYAN, "canceled": MUTED,
    # sessões
    "idle": YELLOW, "problem": RED, "ended": MUTED,
}

STYLESHEET = f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QWidget#sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 18px; font-weight: 700; }}
QLabel#brandSub, QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 12px; }}
QLabel#cardValue {{ font-size: 26px; font-weight: 700; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}

QPushButton#nav {{ text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    background: transparent; color: {MUTED}; font-size: 14px; }}
QPushButton#nav:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT}; color: white; font-weight: 600; }}

QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #6a9dff; }}
QPushButton#danger:hover {{ border-color: {RED}; color: {RED}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT}; }}
QSpinBox, QDoubleSpinBox {{ padding-left: 10px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px; height: 0px; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; outline: none; }}

QTableView, QListWidget {{ background: {PANEL}; alternate-background-color: #181e29;
    border: 1px solid {BORDER}; border-radius: 8px; gridline-color: transparent; outline: none; }}
QTableView::item {{ padding: 4px 8px; border: none; }}
QTableView::item:selected, QListWidget::item:selected {{ background: #26406f; color: white; }}
QListWidget::item {{ padding: 5px 6px; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; padding: 8px; border: none;
    border-bottom: 1px solid {BORDER}; font-weight: 600; }}
QTableCornerButton::section {{ background: {CARD}; border: none; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 8px 16px; border: none; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}

QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding: 14px 12px 10px 12px;
    background: {CARD}; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {MUTED}; }}
QGroupBox QLabel, QGroupBox QCheckBox {{ background: transparent; font-weight: 400; }}

QProgressBar {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 5px; height: 10px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QProgressBar[level="warn"]::chunk {{ background: {YELLOW}; }}
QProgressBar[level="high"]::chunk {{ background: {RED}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER}; border-radius: 4px;
    background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSplitter::handle {{ background: transparent; }}
QMessageBox, QInputDialog {{ background: {BG}; }}
"""
