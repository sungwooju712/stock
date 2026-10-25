# -*- coding: utf-8 -*-
"""Global visual theme for KOSPI 인사이트."""

from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from .constants import COLORS
from .paths import assets_dir


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text_2"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["teal"]))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["navy"]))
    palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor(COLORS["muted_2"]))
    app.setPalette(palette)

    font = QFont("Malgun Gothic", 9)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(stylesheet())


def stylesheet() -> str:
    asset_root = assets_dir().resolve().as_posix()
    check_image = f"{asset_root}/check_white.png"
    down_image = f"{asset_root}/chevron_down.png"
    up_image = f"{asset_root}/chevron_up.png"
    template = Template(
        r"""
* {
    outline: 0;
}
QWidget {
    font-family: "Malgun Gothic", "맑은 고딕", "Segoe UI", sans-serif;
    font-size: 9.5pt;
    color: $text;
}
QMainWindow, QDialog {
    background: $bg;
}
QFrame#ContentRoot, QWidget#PageRoot {
    background: $bg;
}
QFrame#Sidebar {
    background: $navy;
    border: none;
}
QFrame#TopBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid $border;
}
QFrame[card="true"] {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: 14px;
}
QFrame[card="soft"] {
    background: $surface_alt;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame[card="dark"] {
    background: $navy;
    border: 1px solid $navy_2;
    border-radius: 14px;
}
QFrame[card="accent"] {
    background: $teal_soft;
    border: 1px solid #C7EEE7;
    border-radius: 12px;
}
QFrame[hline="true"] {
    background: $border;
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QLabel {
    background: transparent;
    color: $text;
}
QLabel#BrandTitle {
    color: #FFFFFF;
    font-size: 14pt;
    font-weight: 800;
}
QLabel#BrandSub {
    color: #8FA9C1;
    font-size: 8pt;
    font-weight: 500;
}
QLabel#PageTitle {
    color: $text;
    font-size: 21pt;
    font-weight: 800;
}
QLabel#PageSubtitle {
    color: $muted;
    font-size: 9pt;
    font-weight: 500;
}
QLabel#TopTitle {
    color: $text;
    font-size: 14pt;
    font-weight: 800;
}
QLabel#TopSub {
    color: $muted;
    font-size: 8pt;
    font-weight: 500;
}
QLabel#DialogTitle {
    color: $text;
    font-size: 14pt;
    font-weight: 800;
}
QLabel[role="kicker"] {
    color: $muted;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel[role="cardTitle"] {
    color: $text;
    font-size: 11.5pt;
    font-weight: 800;
}
QLabel[role="cardSub"] {
    color: $muted;
    font-size: 8.5pt;
    font-weight: 500;
}
QLabel[role="metricValue"] {
    color: $text;
    font-size: 22pt;
    font-weight: 800;
}
QLabel[role="metricValueSmall"] {
    color: $text;
    font-size: 14pt;
    font-weight: 800;
}
QLabel[role="metricCaption"] {
    color: $muted;
    font-size: 8.5pt;
    font-weight: 500;
}
QLabel[role="sectionLabel"] {
    color: #8FA6BC;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QLabel[role="muted"] {
    color: $muted;
}
QLabel[role="mutedSmall"] {
    color: $muted;
    font-size: 8pt;
}
QLabel[role="tiny"] {
    color: $muted_2;
    font-size: 7.5pt;
}
QLabel[role="valueStrong"] {
    color: $text;
    font-weight: 800;
}
QLabel[role="rowTitle"] {
    color: $text;
    font-size: 10pt;
    font-weight: 700;
}
QLabel[role="sidebarLabel"] {
    color: #6F89A1;
    font-size: 7.5pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel[role="sidebarFooter"] {
    color: #A5BACE;
    font-size: 8pt;
}
QLabel[role="sidebarFooterStrong"] {
    color: #E7F0F8;
    font-size: 8.5pt;
    font-weight: 700;
}
QLabel[color="rise"] {
    color: $rise;
}
QLabel[color="fall"] {
    color: $fall;
}
QLabel[color="flat"] {
    color: $muted;
}
QLabel[color="teal"] {
    color: $teal_dark;
}
QLabel[color="navy"] {
    color: $navy_2;
}
QLabel[color="amber"] {
    color: #C17A0A;
}
QLabel[badge="true"] {
    background: #F1F5F9;
    color: #526273;
    border: 1px solid #E2E8F0;
    border-radius: 11px;
    padding: 3px 9px;
    font-size: 8pt;
    font-weight: 700;
}
QLabel[badge="true"][tone="teal"] {
    background: $teal_soft;
    color: $teal_dark;
    border-color: #C7EEE7;
}
QLabel[badge="true"][tone="amber"] {
    background: $amber_soft;
    color: #A96700;
    border-color: #F7E2B8;
}
QLabel[badge="true"][tone="rise"] {
    background: $positive_soft;
    color: $rise;
    border-color: #FBD5D5;
}
QLabel[badge="true"][tone="fall"] {
    background: $negative_soft;
    color: $fall;
    border-color: #D9E7FF;
}
QLabel[badge="true"][tone="dark"] {
    background: $navy_2;
    color: #EAF2F8;
    border-color: $navy_2;
}
QPushButton {
    background: #FFFFFF;
    color: $text_2;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: 600;
    min-height: 18px;
}
QPushButton:hover {
    background: $surface_alt;
    border-color: $border_dark;
}
QPushButton:pressed {
    background: #EEF3F8;
}
QPushButton:disabled {
    color: #A7B4C2;
    background: #F8FAFC;
    border-color: #EDF1F5;
}
QPushButton[variant="primary"] {
    background: $teal;
    color: #FFFFFF;
    border-color: $teal;
}
QPushButton[variant="primary"]:hover {
    background: $teal_dark;
    border-color: $teal_dark;
}
QPushButton[variant="primary"]:pressed {
    background: #086859;
}
QPushButton[variant="primary"]:disabled {
    background: #A9DED6;
    border-color: #A9DED6;
    color: #F3FFFC;
}
QPushButton[variant="dark"] {
    background: $navy_2;
    color: #FFFFFF;
    border-color: $navy_2;
}
QPushButton[variant="dark"]:hover {
    background: $navy_3;
    border-color: $navy_3;
}
QPushButton[variant="soft"] {
    background: $teal_soft;
    color: $teal_dark;
    border-color: #D3F1EA;
}
QPushButton[variant="soft"]:hover {
    background: #DCF5EF;
    border-color: #BEE9E0;
}
QPushButton[variant="ghost"] {
    background: transparent;
    border: none;
    padding: 6px;
    color: $muted;
}
QPushButton[variant="ghost"]:hover {
    background: #F1F5F9;
    color: $text;
}
QPushButton[variant="danger"] {
    background: #FFFFFF;
    color: $rise;
    border-color: #F3D4D4;
}
QPushButton[variant="danger"]:hover {
    background: $positive_soft;
}
QPushButton[variant="link"] {
    background: transparent;
    border: none;
    padding: 2px 0;
    color: $teal_dark;
    font-weight: 700;
}
QPushButton[variant="link"]:hover {
    color: $teal;
    text-decoration: underline;
}
QPushButton[variant="chip"] {
    background: #FFFFFF;
    color: $text_2;
    border: 1px solid $border;
    border-radius: 13px;
    padding: 5px 11px;
    font-size: 8.5pt;
    font-weight: 600;
    min-height: 16px;
}
QPushButton[variant="chip"]:hover {
    border-color: $teal;
    color: $teal_dark;
    background: $teal_soft;
}
QPushButton[iconOnly="true"] {
    padding: 6px;
    min-width: 22px;
    min-height: 22px;
}
QPushButton[segmented="true"] {
    background: transparent;
    border: none;
    border-radius: 7px;
    color: $muted;
    padding: 6px 12px;
    font-size: 8.5pt;
    font-weight: 700;
}
QPushButton[segmented="true"]:hover {
    background: rgba(255, 255, 255, 150);
    color: $text;
}
QPushButton[segmented="true"]:checked {
    background: #FFFFFF;
    color: $navy_2;
    border: 1px solid $border;
}
QPushButton[segmented="true"]:checked:hover {
    background: #FFFFFF;
}
QFrame[segmented="container"] {
    background: #F1F5F9;
    border: 1px solid #E8EEF4;
    border-radius: 9px;
}
QPushButton[nav="true"] {
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 8px;
    color: #A5BACE;
    text-align: left;
    padding: 9px 10px 9px 11px;
    font-size: 9.5pt;
    font-weight: 600;
}
QPushButton[nav="true"]:hover {
    background: #13314D;
    color: #FFFFFF;
}
QPushButton[nav="true"]:checked {
    background: #173B59;
    border-left: 3px solid $teal;
    color: #FFFFFF;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 18px;
    selection-background-color: $teal;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: $border_dark;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid $teal;
}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #F8FAFC;
    color: #A7B4C2;
    border-color: #EDF1F5;
}
QLineEdit[search="true"] {
    padding-left: 8px;
}
QComboBox::drop-down, QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow, QDateEdit::down-arrow {
    image: url("$down_image");
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: $teal_soft;
    selection-color: $navy_2;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 3px 8px;
    border-radius: 5px;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background: transparent;
}
QAbstractSpinBox::up-button {
    subcontrol-position: top right;
    margin: 2px 2px 0 0;
}
QAbstractSpinBox::down-button {
    subcontrol-position: bottom right;
    margin: 0 2px 2px 0;
}
QAbstractSpinBox::up-arrow {
    image: url("$up_image");
    width: 9px;
    height: 9px;
}
QAbstractSpinBox::down-arrow {
    image: url("$down_image");
    width: 9px;
    height: 9px;
}
QCheckBox {
    color: $text_2;
    spacing: 8px;
    font-weight: 600;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid $border_dark;
    border-radius: 4px;
    background: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: $teal;
}
QCheckBox::indicator:checked {
    background: $teal;
    border-color: $teal;
    image: url("$check_image");
}
QCheckBox:disabled {
    color: #A7B4C2;
}
QTableView, QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: none;
    gridline-color: transparent;
    selection-background-color: $teal_soft;
    selection-color: $text;
    outline: 0;
}
QTableView::item, QTableWidget::item {
    padding: 7px 7px;
    border: none;
    border-bottom: 1px solid #EDF1F5;
}
QTableView::item:hover, QTableWidget::item:hover {
    background: #F7FBFF;
}
QTableView::item:selected, QTableWidget::item:selected {
    background: $teal_soft;
    color: $text;
}
QListWidget {
    background: transparent;
    border: none;
    outline: 0;
}
QListWidget#WatchList::item {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    margin: 2px 0;
    padding: 5px 6px;
}
QListWidget#WatchList::item:hover {
    background: #F7FAFC;
    border-color: #EDF2F7;
}
QListWidget#WatchList::item:selected {
    background: $teal_soft;
    border-color: #C7EEE7;
    color: $text;
}
QListWidget#WatchList::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_dark;
    border-radius: 4px;
    background: #FFFFFF;
}
QListWidget#WatchList::indicator:hover {
    border-color: $teal;
}
QListWidget#WatchList::indicator:checked {
    background: $teal;
    border-color: $teal;
    image: url("$check_image");
}
QListWidget#StockResultList {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 3px;
}
QListWidget#StockResultList::item {
    border-radius: 8px;
    margin: 1px;
    border: 1px solid transparent;
}
QListWidget#StockResultList::item:hover {
    background: #F8FAFC;
    border-color: #EDF2F7;
}
QListWidget#StockResultList::item:selected {
    background: $teal_soft;
    border-color: #C7EEE7;
}
QFrame#SidebarCard {
    background: $navy_2;
    border: 1px solid $navy_3;
    border-radius: 11px;
}
QFrame[card="dark"] QLabel {
    color: #EAF2F8;
}
QLabel#HeroName {
    color: #FFFFFF;
    font-size: 20pt;
    font-weight: 800;
}
QLabel#HeroMeta {
    color: #9DB3C7;
    font-size: 8.5pt;
    font-weight: 500;
}
QLabel#HeroPrice {
    color: #FFFFFF;
    font-size: 26pt;
    font-weight: 800;
}
QFrame#TopBar QLabel[badge="true"] {
    background: #F1F5F9;
    color: #526273;
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: #F8FAFC;
    color: #64748B;
    border: none;
    border-bottom: 1px solid $border;
    padding: 9px 7px;
    font-size: 8pt;
    font-weight: 700;
}
QHeaderView::section:first {
    border-top-left-radius: 8px;
}
QHeaderView::section:last {
    border-top-right-radius: 8px;
}
QTableCornerButton::section {
    background: #F8FAFC;
    border: none;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #CBD5E1;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #94A3B8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: transparent;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QToolTip {
    background: $navy;
    color: #FFFFFF;
    border: none;
    border-radius: 7px;
    padding: 7px 9px;
    font-size: 8.5pt;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 24px 7px 12px;
    border-radius: 5px;
    color: $text_2;
}
QMenu::item:selected {
    background: $teal_soft;
    color: $navy_2;
}
QMenu::separator {
    height: 1px;
    background: $border;
    margin: 5px 8px;
}
QProgressBar {
    background: #E9EFF5;
    border: none;
    border-radius: 5px;
    height: 9px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: $teal;
    border-radius: 5px;
}
QSplitter::handle {
    background: transparent;
}
QStatusBar {
    background: #FFFFFF;
    color: $muted;
    border-top: 1px solid $border;
}
QDialog {
    background: #FFFFFF;
}
QFrame#ToastFrame {
    border-radius: 11px;
}
QDateEdit QCalendarWidget, QCalendarWidget {
    background: #FFFFFF;
    border: 1px solid $border;
}
"""
    )
    return template.substitute(
        bg=COLORS["bg"],
        surface=COLORS["surface"],
        surface_alt=COLORS["surface_alt"],
        border=COLORS["border"],
        border_dark=COLORS["border_dark"],
        text=COLORS["text"],
        text_2=COLORS["text_2"],
        muted=COLORS["muted"],
        muted_2=COLORS["muted_2"],
        navy=COLORS["navy"],
        navy_2=COLORS["navy_2"],
        navy_3=COLORS["navy_3"],
        teal=COLORS["teal"],
        teal_dark=COLORS["teal_dark"],
        teal_soft=COLORS["teal_soft"],
        amber=COLORS["amber"],
        amber_soft=COLORS["amber_soft"],
        rise=COLORS["rise"],
        fall=COLORS["fall"],
        positive_soft=COLORS["positive_soft"],
        negative_soft=COLORS["negative_soft"],
        check_image=check_image,
        down_image=down_image,
        up_image=up_image,
    )
