# -*- coding: utf-8 -*-
"""Reusable UI building blocks and small custom-painted widgets."""

from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .constants import COLORS
from .formatters import tone_class
from .icons import icon, pixmap


def set_prop(widget: QWidget, name: str, value) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def make_button(
    text: str,
    *,
    icon_name: str | None = None,
    icon_color: str = COLORS["text_2"],
    variant: str = "secondary",
    parent: QWidget | None = None,
) -> QPushButton:
    button = QPushButton(text, parent)
    button.setCursor(Qt.PointingHandCursor)
    if icon_name:
        button.setIcon(icon(icon_name, icon_color, 17))
    if variant != "secondary":
        button.setProperty("variant", variant)
    return button


def make_icon_button(
    name: str,
    tooltip: str,
    *,
    color: str = COLORS["muted"],
    variant: str = "ghost",
    parent: QWidget | None = None,
    size: int = 18,
) -> QPushButton:
    button = QPushButton(parent)
    button.setIcon(icon(name, color, size))
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setProperty("iconOnly", True)
    if variant != "secondary":
        button.setProperty("variant", variant)
    return button


def hline(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setProperty("hline", True)
    line.setFrameShape(QFrame.NoFrame)
    return line


class Card(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        padding: int | tuple[int, int, int, int] = 18,
        spacing: int = 12,
        variant: str = "true",
    ):
        super().__init__(parent)
        self.setProperty("card", variant)
        self.body = QVBoxLayout(self)
        if isinstance(padding, int):
            self.body.setContentsMargins(padding, padding, padding, padding)
        else:
            self.body.setContentsMargins(*padding)
        self.body.setSpacing(spacing)


class SectionHeader(QWidget):
    """Title/subtitle block with an optional trailing widget/actions."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        parent: QWidget | None = None,
        trailing: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "cardTitle")
        text_box.addWidget(self.title_label)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("role", "cardSub")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        text_box.addWidget(self.subtitle_label)
        layout.addLayout(text_box, 1)
        self.trailing = trailing
        if trailing is not None:
            layout.addWidget(trailing, 0, Qt.AlignTop)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))


class Badge(QLabel):
    def __init__(self, text: str = "", tone: str = "default", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setProperty("badge", True)
        if tone != "default":
            self.setProperty("tone", tone)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        set_prop(self, "tone", tone)


class IconCircle(QLabel):
    def __init__(
        self,
        icon_name: str,
        *,
        color: str = COLORS["teal"],
        soft: str = COLORS["teal_soft"],
        size: int = 38,
        icon_size: int = 19,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setPixmap(pixmap(icon_name, color, icon_size))
        self.setStyleSheet(
            f"background: {soft}; border: none; border-radius: {size // 2}px;"
        )


class KpiCard(Card):
    def __init__(
        self,
        kicker: str,
        value: str,
        caption: str,
        icon_name: str,
        *,
        accent: str = COLORS["teal"],
        soft: str = COLORS["teal_soft"],
        parent: QWidget | None = None,
    ):
        super().__init__(parent, padding=(16, 14, 16, 14), spacing=4)
        self.setMinimumHeight(108)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        kicker_label = QLabel(kicker)
        kicker_label.setProperty("role", "kicker")
        top.addWidget(kicker_label)
        top.addStretch(1)
        top.addWidget(IconCircle(icon_name, color=accent, soft=soft, size=34, icon_size=17))
        self.body.addLayout(top)
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "metricValue")
        self.body.addWidget(self.value_label)
        self.caption_label = QLabel(caption)
        self.caption_label.setProperty("role", "metricCaption")
        self.caption_label.setWordWrap(True)
        self.body.addWidget(self.caption_label)
        self.body.addStretch(1)

    def set_data(self, value: str, caption: str | None = None, tone: str | None = None) -> None:
        self.value_label.setText(value)
        if caption is not None:
            self.caption_label.setText(caption)
        if tone is not None:
            set_prop(self.caption_label, "color", tone)
            if tone == "muted":
                self.caption_label.setProperty("color", "")


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(
        self,
        items: Sequence[tuple[str, str]],
        *,
        current: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("segmented", "container")
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(1)
        for index, (key, label) in enumerate(items):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("segmented", True)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            if compact:
                button.setStyleSheet("padding: 5px 10px;")
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons[key] = button
        self.current_key = current or items[0][0]
        if self.current_key in self._buttons:
            self._buttons[self.current_key].setChecked(True)
        self._group.idClicked.connect(self._on_clicked)

    def _on_clicked(self, index: int) -> None:
        button = self._group.button(index)
        if button is None:
            return
        for key, candidate in self._buttons.items():
            if candidate is button:
                self.current_key = key
                self.changed.emit(key)
                break

    def set_current(self, key: str, *, emit: bool = False) -> None:
        button = self._buttons.get(key)
        if button and not button.isChecked():
            button.setChecked(True)
            self.current_key = key
            if emit:
                self.changed.emit(key)


class SearchEdit(QLineEdit):
    def __init__(self, placeholder: str = "검색", parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("search", True)
        self.setPlaceholderText(placeholder)
        self.addAction(icon("search", COLORS["muted_2"], 17), QLineEdit.LeadingPosition)
        self.setClearButtonEnabled(True)


class MetricTile(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "–",
        *,
        note: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("card", "soft")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)
        label_widget = QLabel(label)
        label_widget.setProperty("role", "mutedSmall")
        layout.addWidget(label_widget)
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "metricValueSmall")
        layout.addWidget(self.value_label)
        self.note_label = QLabel(note)
        self.note_label.setProperty("role", "tiny")
        self.note_label.setWordWrap(True)
        self.note_label.setVisible(bool(note))
        layout.addWidget(self.note_label)

    def set_value(self, value: str, note: str | None = None, color: str | None = None) -> None:
        self.value_label.setText(value)
        if note is not None:
            self.note_label.setText(note)
            self.note_label.setVisible(bool(note))
        if color:
            self.value_label.setProperty("color", color)
            set_prop(self.value_label, "color", color)


class EmptyState(QFrame):
    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        icon_name: str = "star",
        action: QPushButton | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("card", "soft")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 34, 28, 34)
        layout.setSpacing(9)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(IconCircle(icon_name, size=46, icon_size=22), 0, Qt.AlignHCenter)
        title_label = QLabel(title)
        title_label.setProperty("role", "cardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        if description:
            desc = QLabel(description)
            desc.setProperty("role", "muted")
            desc.setAlignment(Qt.AlignCenter)
            desc.setWordWrap(True)
            layout.addWidget(desc)
        self.action = action
        if action:
            layout.addSpacing(6)
            layout.addWidget(action, 0, Qt.AlignHCenter)


class StockNameWidget(QWidget):
    def __init__(
        self,
        name: str,
        code: str,
        *,
        secondary: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        primary = QLabel(name)
        primary.setProperty("role", "rowTitle")
        primary.setStyleSheet("font-size: 9.5pt;")
        layout.addWidget(primary)
        detail = QLabel(secondary or code)
        detail.setProperty("role", "tiny")
        layout.addWidget(detail)


class LogoWidget(QWidget):
    def __init__(self, size: int = 42, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#143A58"))
        gradient.setColorAt(1.0, QColor("#0B1F33"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, self.width() * 0.27, self.height() * 0.27)
        painter.setBrush(QColor(15, 157, 138, 55))
        painter.drawEllipse(
            QRectF(self.width() * 0.52, -self.height() * 0.20, self.width() * 0.72, self.height() * 0.65)
        )
        bars = [
            (0.21, 0.60, 0.30, 0.82),
            (0.37, 0.45, 0.46, 0.82),
            (0.53, 0.53, 0.62, 0.82),
            (0.69, 0.31, 0.78, 0.82),
        ]
        for i, (x1, y1, x2, y2) in enumerate(bars):
            color = QColor("#0F9D8A") if i >= 2 else QColor(255, 255, 255, 220)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                QRectF(
                    self.width() * x1,
                    self.height() * y1,
                    self.width() * (x2 - x1),
                    self.height() * (y2 - y1),
                ),
                2.2,
                2.2,
            )
        path = QPainterPath(QPoint(int(self.width() * 0.17), int(self.height() * 0.54)))
        points = [(0.34, 0.42), (0.51, 0.47), (0.70, 0.25), (0.86, 0.17)]
        for x, y in points:
            path.lineTo(self.width() * x, self.height() * y)
        pen = QPen(QColor(COLORS["amber"]), max(2.0, self.width() * 0.035))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setBrush(QColor(COLORS["amber"]))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(
            QPoint(int(self.width() * 0.86), int(self.height() * 0.17)),
            self.width() * 0.055,
            self.width() * 0.055,
        )
        painter.end()


class BreadthBar(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.rising = 0
        self.falling = 0
        self.flat = 0
        self.setMinimumHeight(12)
        self.setMaximumHeight(12)

    def set_values(self, rising: int, falling: int, flat: int) -> None:
        self.rising = max(0, int(rising or 0))
        self.falling = max(0, int(falling or 0))
        self.flat = max(0, int(flat or 0))
        self.update()

    def paintEvent(self, event) -> None:
        total = self.rising + self.falling + self.flat
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 1, self.width(), self.height() - 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#E9EFF5"))
        painter.drawRoundedRect(rect, 5, 5)
        if not total:
            painter.end()
            return
        x = 0.0
        for value, color in (
            (self.rising, COLORS["rise"]),
            (self.flat, "#CBD5E1"),
            (self.falling, COLORS["fall"]),
        ):
            width = rect.width() * value / total
            if width <= 0:
                continue
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, 1, max(1.5, width), rect.height()), 5, 5)
            x += width
        painter.end()


class Toast(QFrame):
    """Dark floating notification with a short fade animation."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("ToastFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMaximumWidth(480)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        layout.addWidget(self.icon_label)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 8.5pt;")
        layout.addWidget(self.text_label, 1)
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity", self)
        self.animation.setDuration(170)
        self.animation.finished.connect(self._hide_if_faded)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, message: str, kind: str = "success", duration: int = 3000) -> None:
        colors = {
            "success": ("#0F9D8A", "check"),
            "error": ("#B42318", "warning"),
            "info": ("#14395A", "info"),
        }
        color, icon_name = colors.get(kind, colors["info"])
        self.setStyleSheet(f"QFrame#ToastFrame {{ background: {color}; border-radius: 11px; }}")
        self.icon_label.setPixmap(pixmap(icon_name, "#FFFFFF", 18))
        self.text_label.setText(message)
        self.setVisible(True)
        self.adjustSize()
        if self.width() > 480:
            self.setFixedWidth(480)
            self.adjustSize()
        self.reposition()
        self.raise_()
        self.animation.stop()
        self.timer.stop()
        self.animation.setStartValue(self.effect.opacity())
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
        self.timer.start(duration)

    def _fade_out(self) -> None:
        self.animation.stop()
        self.animation.setStartValue(self.effect.opacity())
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InCubic)
        self.animation.start()

    def _hide_if_faded(self) -> None:
        if self.effect.opacity() <= 0.01:
            self.hide()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        x = max(16, parent.width() - self.width() - 26)
        y = 84
        self.move(QPoint(x, y))


def run_delayed(milliseconds: int, owner: QObject, callback) -> QTimer:
    timer = QTimer(owner)
    timer.setSingleShot(True)
    timer.timeout.connect(callback)
    timer.start(milliseconds)
    return timer
