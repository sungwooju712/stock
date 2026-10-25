# -*- coding: utf-8 -*-
"""Custom interactive multi-series price chart.

The chart is intentionally dependency-free beyond Qt: crisp high-DPI drawing,
hover crosshair, clickable legend toggles and period-aware axis labels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .constants import COLORS
from .icons import pixmap


@dataclass
class LegendItem:
    code: str
    name: str
    color: str
    rect: QRectF


class PerformanceChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.payload: dict[str, Any] = {"categories": [], "series": [], "mode": "price", "period": "full"}
        self.hidden_codes: set[str] = set()
        self._legend_items: list[LegendItem] = []
        self._hover_index: int | None = None
        self._plot = QRectF()
        self._x_positions: list[float] = []
        self._y_min = 0.0
        self._y_max = 1.0
        self._ticks: list[float] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)

    def set_payload(self, payload: dict[str, Any]) -> None:
        categories = payload.get("categories") or []
        series = payload.get("series") or []
        current_codes = {item.get("code") for item in series}
        if set(self.hidden_codes) - current_codes:
            self.hidden_codes &= current_codes
        self.payload = payload
        self._hover_index = None
        self.update()

    def set_hidden(self, codes: set[str]) -> None:
        self.hidden_codes = set(codes)
        self.update()

    def visible_series(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.payload.get("series") or []
            if item.get("code") not in self.hidden_codes
        ]

    def sizeHint(self):
        return self.minimumSize().expandedTo(self._size_hint())

    def _size_hint(self):
        from PySide6.QtCore import QSize

        return QSize(760, 330)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.fillRect(self.rect(), Qt.transparent)
        categories = self.payload.get("categories") or []
        series = self.payload.get("series") or []
        visible = self.visible_series()

        if not categories or not series:
            self._draw_empty(painter, "표시할 종가 데이터가 없습니다", "데이터를 새로고침하거나 다른 종목을 선택하세요.")
            painter.end()
            return
        if not visible:
            self._draw_empty(painter, "모든 종목이 숨겨졌습니다", "위 범례를 눌러 종목을 다시 표시할 수 있습니다.")
            painter.end()
            return

        legend_rows = self._layout_legend(painter, series)
        top = 14 + legend_rows * 21
        left = 60
        right = 18
        bottom = 36
        plot_width = max(40.0, self.width() - left - right)
        plot_height = max(60.0, self.height() - top - bottom)
        self._plot = QRectF(left, top, plot_width, plot_height)
        self._draw_legend(painter, series)
        self._compute_scale(visible)
        self._draw_grid(painter, categories)
        self._draw_series(painter, categories, visible)
        self._draw_x_labels(painter, categories)
        if self._hover_index is not None:
            self._draw_hover(painter, categories, visible)
        painter.end()

    def _draw_empty(self, painter: QPainter, title: str, description: str) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#FAFCFE"))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        icon_pixmap = pixmap("chart", COLORS["muted_2"], 34)
        painter.drawPixmap(
            QPoint(int(self.width() / 2 - 17), int(self.height() / 2 - 52)), icon_pixmap
        )
        painter.setPen(QColor(COLORS["text_2"]))
        title_font = QFont("Malgun Gothic", 10)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(0, self.height() / 2 - 6, self.width(), 28),
            Qt.AlignHCenter | Qt.AlignVCenter,
            title,
        )
        painter.setFont(QFont("Malgun Gothic", 8))
        painter.setPen(QColor(COLORS["muted"]))
        painter.drawText(
            QRectF(40, self.height() / 2 + 22, self.width() - 80, 42),
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
            description,
        )

    def _layout_legend(self, painter: QPainter, series: list[dict[str, Any]]) -> int:
        font = QFont("Malgun Gothic", 8)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        x = 18.0
        y = 11.0
        max_x = self.width() - 18
        row = 0
        self._legend_items = []
        for item in series:
            name = str(item.get("name") or item.get("code"))
            width = 15 + min(metrics.horizontalAdvance(name), 150)
            if x + width > max_x and x > 18:
                x = 18.0
                y += 21
                row += 1
            rect = QRectF(x, y - 2, width + 5, 20)
            self._legend_items.append(
                LegendItem(
                    code=str(item.get("code")),
                    name=name,
                    color=str(item.get("color") or COLORS["teal"]),
                    rect=rect,
                )
            )
            x += width + 20
        return row + 1

    def _draw_legend(self, painter: QPainter, series: list[dict[str, Any]]) -> None:
        font = QFont("Malgun Gothic", 8)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        for item in self._legend_items:
            hidden = item.code in self.hidden_codes
            rect = item.rect
            color = QColor(item.color)
            if hidden:
                color.setAlpha(70)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(rect.left() + 5, rect.center().y()), 4.0, 4.0)
            painter.setPen(QColor(COLORS["muted_2"] if hidden else COLORS["text_2"]))
            painter.drawText(
                QRectF(rect.left() + 14, rect.top(), rect.width() - 14, rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                item.name,
            )
            if hidden:
                painter.setPen(QPen(QColor(COLORS["muted_2"]), 1))
                text_width = min(
                    QFontMetrics(font).horizontalAdvance(item.name), int(rect.width() - 16)
                )
                mid = rect.center().y()
                painter.drawLine(
                    QPointF(rect.left() + 14, mid),
                    QPointF(rect.left() + 14 + text_width, mid),
                )

    def _compute_scale(self, visible: list[dict[str, Any]]) -> None:
        values: list[float] = []
        for item in visible:
            values.extend(
                float(value)
                for value in item.get("values") or []
                if value is not None and math.isfinite(float(value))
            )
        mode = self.payload.get("mode", "price")
        if not values:
            self._y_min, self._y_max = 0.0, 1.0
            self._ticks = [0.0, 1.0]
            return
        low = min(values)
        high = max(values)
        if mode == "return":
            low = min(low, 0.0)
            high = max(high, 0.0)
        if high == low:
            delta = abs(high) * 0.05 or 1.0
            low -= delta
            high += delta
        padding = (high - low) * 0.07
        low -= padding
        high += padding
        step = self._nice_step((high - low) / 4)
        low = math.floor(low / step) * step
        high = math.ceil(high / step) * step
        ticks = []
        tick = low
        while tick <= high + step * 0.4:
            ticks.append(tick)
            tick += step
        self._y_min = low
        self._y_max = high
        self._ticks = ticks

    @staticmethod
    def _nice_step(raw: float) -> float:
        if raw <= 0:
            return 1.0
        magnitude = 10 ** math.floor(math.log10(raw))
        normalized = raw / magnitude
        if normalized <= 1:
            nice = 1
        elif normalized <= 2:
            nice = 2
        elif normalized <= 2.5:
            nice = 2.5
        elif normalized <= 5:
            nice = 5
        else:
            nice = 10
        return nice * magnitude

    def _x_for_index(self, index: int, count: int) -> float:
        if count <= 1:
            return self._plot.center().x()
        return self._plot.left() + self._plot.width() * index / (count - 1)

    def _draw_grid(self, painter: QPainter, categories: list[str]) -> None:
        painter.save()
        painter.setClipRect(self._plot.adjusted(-1, -1, 1, 1))
        grid_pen = QPen(QColor("#EDF2F7"), 1)
        grid_pen.setStyle(Qt.SolidLine)
        for tick in self._ticks:
            y = self._map_y(tick)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(self._plot.left(), y), QPointF(self._plot.right(), y))
        if self.payload.get("mode") == "return" and self._y_min <= 0 <= self._y_max:
            zero_y = self._map_y(0)
            zero_pen = QPen(QColor("#B9C7D5"), 1)
            zero_pen.setStyle(Qt.DashLine)
            painter.setPen(zero_pen)
            painter.drawLine(QPointF(self._plot.left(), zero_y), QPointF(self._plot.right(), zero_y))
        painter.restore()

        font = QFont("Malgun Gothic", 7.5)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["muted"]))
        for tick in self._ticks:
            y = self._map_y(tick)
            label = self._format_axis_value(tick)
            painter.drawText(
                QRectF(0, y - 9, self._plot.left() - 9, 18),
                Qt.AlignRight | Qt.AlignVCenter,
                label,
            )

    def _draw_series(self, painter: QPainter, categories: list[str], visible: list[dict[str, Any]]) -> None:
        painter.save()
        painter.setClipRect(self._plot.adjusted(-2, -2, 2, 2))
        count = len(categories)
        self._x_positions = [self._x_for_index(index, count) for index in range(count)]
        draw_markers = count <= 80
        multi = len(visible) > 1
        for item in visible:
            values = item.get("values") or []
            color = QColor(str(item.get("color") or COLORS["teal"]))
            if not color.isValid():
                color = QColor(COLORS["teal"])
            segments: list[list[QPointF]] = []
            segment: list[QPointF] = []
            for index, value in enumerate(values):
                if value is None or not isinstance(value, (int, float)):
                    if segment:
                        segments.append(segment)
                        segment = []
                    continue
                point = QPointF(self._x_positions[index], self._map_y(float(value)))
                segment.append(point)
            if segment:
                segments.append(segment)
            if not multi:
                for points in segments:
                    if len(points) < 2:
                        continue
                    area = QPainterPath(points[0])
                    for point in points[1:]:
                        area.lineTo(point)
                    last = points[-1]
                    area.lineTo(QPointF(last.x(), self._plot.bottom()))
                    area.lineTo(QPointF(points[0].x(), self._plot.bottom()))
                    area.closeSubpath()
                    gradient = QLinearGradient(0, self._plot.top(), 0, self._plot.bottom())
                    base = QColor(color)
                    base.setAlpha(50)
                    transparent = QColor(color)
                    transparent.setAlpha(4)
                    gradient.setColorAt(0, base)
                    gradient.setColorAt(1, transparent)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(gradient)
                    painter.drawPath(area)
            pen = QPen(color, 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for points in segments:
                if len(points) == 1:
                    painter.setBrush(color)
                    painter.drawEllipse(points[0], 2.5, 2.5)
                    painter.setBrush(Qt.NoBrush)
                    continue
                path = QPainterPath(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                painter.drawPath(path)
                if draw_markers:
                    painter.setBrush(QColor("#FFFFFF"))
                    painter.setPen(QPen(color, 1.3))
                    for point in points:
                        painter.drawEllipse(point, 2.5, 2.5)
                    painter.setBrush(Qt.NoBrush)
            # End cap marker.
            for points in segments:
                if points:
                    painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                    painter.setBrush(color)
                    painter.drawEllipse(points[-1], 3.8, 3.8)
        painter.restore()

    def _draw_x_labels(self, painter: QPainter, categories: list[str]) -> None:
        count = len(categories)
        if not count:
            return
        if count <= 6:
            indices = list(range(count))
        else:
            indices = sorted({round(i * (count - 1) / 5) for i in range(6)})
        font = QFont("Malgun Gothic", 7.5)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["muted"]))
        metrics = QFontMetrics(font)
        for index in indices:
            x = self._x_for_index(index, count)
            label = self._format_x(categories[index])
            width = metrics.horizontalAdvance(label) + 10
            left = x - width / 2
            left = max(self._plot.left() - 5, min(left, self._plot.right() - width + 5))
            painter.drawText(
                QRectF(left, self._plot.bottom() + 9, width, 18),
                Qt.AlignHCenter | Qt.AlignTop,
                label,
            )
            painter.setPen(QPen(QColor("#DCE5EE"), 1))
            painter.drawLine(
                QPointF(x, self._plot.bottom()),
                QPointF(x, self._plot.bottom() + 3),
            )
            painter.setPen(QColor(COLORS["muted"]))
        unit = "수익률 (%)" if self.payload.get("mode") == "return" else "종가 (원)"
        painter.setFont(QFont("Malgun Gothic", 7))
        painter.setPen(QColor(COLORS["muted_2"]))
        painter.drawText(
            QRectF(self._plot.left(), self._plot.top() - 15, self._plot.width(), 14),
            Qt.AlignRight | Qt.AlignBottom,
            unit,
        )

    def _draw_hover(self, painter: QPainter, categories: list[str], visible: list[dict[str, Any]]) -> None:
        index = self._hover_index
        if index is None or not (0 <= index < len(categories)):
            return
        x = self._x_for_index(index, len(categories))
        painter.save()
        pen = QPen(QColor("#B8C7D6"), 1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, self._plot.top()), QPointF(x, self._plot.bottom()))

        tooltip_rows: list[tuple[str, QColor, str]] = []
        for item in visible:
            values = item.get("values") or []
            if index >= len(values) or values[index] is None:
                continue
            value = float(values[index])
            point = QPointF(x, self._map_y(value))
            color = QColor(str(item.get("color") or COLORS["teal"]))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
            painter.setBrush(color)
            painter.drawEllipse(point, 3.6, 3.6)
            tooltip_rows.append(
                (
                    str(item.get("name") or item.get("code")),
                    color,
                    self._format_value(value),
                )
            )
        painter.restore()
        if not tooltip_rows:
            return
        bold_font = QFont("Malgun Gothic", 8)
        bold_font.setWeight(QFont.DemiBold)
        metrics = QFontMetrics(bold_font)
        date_label = self._format_tooltip_date(categories[index])
        widths = [metrics.horizontalAdvance(name) + metrics.horizontalAdvance(value) + 44 for name, _, value in tooltip_rows]
        width = max(widths + [metrics.horizontalAdvance(date_label) + 28, 160])
        width = min(width, 320)
        row_height = 18
        height = 14 + 21 + len(tooltip_rows) * row_height + 6
        box_x = x + 16
        if box_x + width > self.width() - 8:
            box_x = x - width - 16
        box_x = max(8.0, box_x)
        box_y = self._plot.top() + 8
        box = QRectF(box_x, box_y, width, height)
        painter.save()
        shadow = QColor(11, 31, 51, 22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow)
        painter.drawRoundedRect(box.adjusted(2, 3, 2, 3), 8, 8)
        painter.setBrush(QColor(11, 31, 51, 242))
        painter.drawRoundedRect(box, 8, 8)
        painter.setPen(QColor("#93A7BB"))
        painter.setFont(QFont("Malgun Gothic", 7.5))
        painter.drawText(
            QRectF(box.left() + 12, box.top() + 8, width - 24, 16),
            Qt.AlignVCenter,
            date_label,
        )
        painter.setFont(bold_font)
        y = box.top() + 29
        for name, color, value in tooltip_rows[:10]:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(box.left() + 14, y + 8), 3.2, 3.2)
            painter.setPen(QColor("#DCE7F1"))
            painter.drawText(
                QRectF(box.left() + 23, y, width * 0.55, row_height),
                Qt.AlignVCenter | Qt.AlignLeft,
                name,
            )
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                QRectF(box.left() + width * 0.50, y, width * 0.48 - 12, row_height),
                Qt.AlignVCenter | Qt.AlignRight,
                value,
            )
            y += row_height
        painter.restore()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        for item in self._legend_items:
            if item.rect.contains(pos):
                self.setCursor(Qt.PointingHandCursor)
                self._hover_index = None
                self.update()
                return
        if self._plot.contains(pos) and self._x_positions:
            self.setCursor(Qt.CrossCursor)
            count = len(self._x_positions)
            if count <= 1:
                index = 0
            else:
                ratio = (pos.x() - self._plot.left()) / max(1.0, self._plot.width())
                index = int(round(ratio * (count - 1)))
                index = max(0, min(count - 1, index))
            if index != self._hover_index:
                self._hover_index = index
                self.update()
        else:
            self.setCursor(Qt.ArrowCursor)
            if self._hover_index is not None:
                self._hover_index = None
                self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_index = None
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        for item in self._legend_items:
            if item.rect.contains(pos):
                if item.code in self.hidden_codes:
                    self.hidden_codes.remove(item.code)
                else:
                    self.hidden_codes.add(item.code)
                self.update()
                break
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _map_y(self, value: float) -> float:
        span = self._y_max - self._y_min
        if span == 0:
            return self._plot.center().y()
        return self._plot.bottom() - (value - self._y_min) / span * self._plot.height()

    def _format_axis_value(self, value: float) -> str:
        if self.payload.get("mode") == "return":
            return f"{value:+.0f}%" if abs(value) >= 0.5 else "0%"
        if abs(value) >= 100_000_000:
            return f"{value / 100_000_000:,.1f}억"
        if abs(value) >= 10_000:
            if abs(value) < 100_000:
                return f"{value / 10_000:,.1f}만"
            return f"{value / 10_000:,.0f}만"
        return f"{value:,.0f}"

    def _format_value(self, value: float) -> str:
        if self.payload.get("mode") == "return":
            return f"{value:+.2f}%"
        return f"{value:,.0f}원"

    def _format_x(self, category: str) -> str:
        period = self.payload.get("period")
        text = str(category)
        if period == "annual":
            return text
        if period == "monthly":
            return text
        if len(text) >= 10:
            if period == "recent":
                return text[5:10]
            if len(self.payload.get("categories") or []) >= 180:
                return text[:7]
            return text[5:10]
        return text

    def _format_tooltip_date(self, category: str) -> str:
        text = str(category)
        if self.payload.get("period") == "monthly":
            return f"{text[:4]}년 {text[5:]}월"
        if self.payload.get("period") == "annual":
            return f"{text}년"
        if len(text) == 10:
            return f"{text[:4]}년 {text[5:7]}월 {text[8:10]}일"
        return text
