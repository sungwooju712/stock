# -*- coding: utf-8 -*-
"""Background task execution and the modal progress dialog."""

from __future__ import annotations

import threading
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .constants import COLORS
from .icons import pixmap
from .widgets import IconCircle, make_button


class TaskSignals(QObject):
    progress = Signal(str, int, int)
    finished = Signal(object)
    failed = Signal(str, str)
    cancelled = Signal()
    done = Signal()


class BackgroundTask(QRunnable):
    """Run a callable in the thread pool.

    The callable receives ``(progress, cancel_event)``.  All GUI updates must
    happen in callbacks connected on the main thread.
    """

    def __init__(self, function: Callable[[Callable[[str, int, int], None], threading.Event], Any]):
        super().__init__()
        self.function = function
        self.cancel_event = threading.Event()
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        def report(message: str, done: int, total: int) -> None:
            if not self.cancel_event.is_set():
                self.signals.progress.emit(str(message), int(done), int(total))

        try:
            result = self.function(report, self.cancel_event)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI with details
            self.signals.failed.emit(str(exc) or exc.__class__.__name__, traceback.format_exc())
        else:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.finished.emit(result)
        finally:
            self.signals.done.emit()


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        cancellable: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setFixedWidth(490)
        self.setModal(True)
        self._running = True
        self._cancellable = cancellable
        self._cancelled = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(
            IconCircle("refresh", color=COLORS["teal"], soft=COLORS["teal_soft"], size=42, icon_size=20),
            0,
            Qt.AlignTop,
        )
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13pt; font-weight: 800; color: #122033;")
        text_box.addWidget(title_label)
        if description:
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #64748B; font-size: 8.5pt;")
            text_box.addWidget(description_label)
        header.addLayout(text_box, 1)
        outer.addLayout(header)

        self.message_label = QLabel("작업을 준비하는 중입니다…")
        self.message_label.setStyleSheet("color: #334155; font-weight: 600; font-size: 8.5pt;")
        outer.addWidget(self.message_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(9)
        outer.addWidget(self.progress)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.percent_label = QLabel("")
        self.percent_label.setStyleSheet("color: #94A3B8; font-size: 8pt;")
        footer.addWidget(self.percent_label)
        footer.addStretch(1)
        self.cancel_button = make_button("취소", variant="secondary")
        self.cancel_button.clicked.connect(self._request_cancel)
        self.cancel_button.setVisible(cancellable)
        footer.addWidget(self.cancel_button)
        outer.addLayout(footer)

    # ------------------------------------------------------------------
    def set_progress(self, message: str, done: int, total: int) -> None:
        if self._cancelled:
            return
        if message:
            self.message_label.setText(message)
        if total > 0:
            self.progress.setRange(0, total)
            value = max(0, min(total, done))
            self.progress.setValue(value)
            self.percent_label.setText(f"{value / total * 100:,.0f}%")
        else:
            self.progress.setRange(0, 0)
            self.percent_label.setText("")

    def finish(self) -> None:
        self._running = False
        if self.progress.maximum() > 0:
            self.progress.setValue(self.progress.maximum())
        self.accept()

    def _request_cancel(self) -> None:
        if not self._running or self._cancelled:
            return
        self._cancelled = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("취소 중…")
        self.message_label.setText("현재 작업을 마무리한 뒤 취소합니다…")
        self.cancel_requested.emit()

    def reject(self) -> None:
        if self._running and self._cancellable:
            self._request_cancel()
            return
        super().reject()


class TaskManager(QObject):
    """Single-task coordinator with progress dialog and Korean error reporting."""

    busy_changed = Signal(bool)
    message = Signal(str, str)
    error = Signal(str, str, str, bool)  # title, summary, details, quiet

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.parent_widget = parent
        self._record: dict[str, Any] | None = None

    @property
    def busy(self) -> bool:
        return self._record is not None

    def run(
        self,
        title: str,
        description: str,
        function: Callable[[Callable[[str, int, int], None], threading.Event], Any],
        *,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        cancellable: bool = True,
        show_dialog: bool = True,
    ) -> bool:
        if self._record is not None:
            self.message.emit("이미 데이터 작업이 진행 중입니다.", "info")
            return False

        task = BackgroundTask(function)
        dialog = None
        if show_dialog:
            dialog = ProgressDialog(
                title,
                description,
                cancellable=cancellable,
                parent=self.parent_widget,
            )
            dialog.cancel_requested.connect(task.cancel)

        record = {
            "task": task,
            "dialog": dialog,
            "title": title,
            "on_success": on_success,
            "on_error": on_error,
            "quiet": not show_dialog,
        }
        self._record = record
        self.busy_changed.emit(True)

        task.signals.progress.connect(
            lambda message, done, total: self._on_progress(message, done, total)
        )
        task.signals.finished.connect(
            lambda result: self._on_finished(result)
        )
        task.signals.failed.connect(
            lambda summary, details: self._on_failed(summary, details)
        )
        task.signals.cancelled.connect(self._on_cancelled)
        task.signals.done.connect(lambda: self._on_done(task))

        QThreadPool.globalInstance().start(task)
        if dialog is not None:
            dialog.show()
        return True

    # ------------------------------------------------------------------
    def _on_progress(self, message: str, done: int, total: int) -> None:
        record = self._record
        if not record:
            return
        dialog = record.get("dialog")
        if dialog is not None:
            dialog.set_progress(message, done, total)

    def cancel_current(self) -> None:
        record = self._record
        if record is not None:
            record["task"].cancel()

    def _finalize(self, record: dict[str, Any]) -> None:
        if self._record is not record:
            return
        dialog = record.get("dialog")
        if dialog is not None:
            try:
                dialog.finish()
                dialog.deleteLater()
            except RuntimeError:
                pass
        self._record = None
        self.busy_changed.emit(False)

    def _on_finished(self, result: Any) -> None:
        record = self._record
        if not record:
            return
        self._finalize(record)
        callback = record.get("on_success")
        if callback is not None:
            try:
                callback(result)
            except Exception as exc:  # noqa: BLE001
                self.error.emit(
                    record.get("title", "작업"),
                    f"결과 처리 중 오류가 발생했습니다: {exc}",
                    traceback.format_exc(),
                    bool(record.get("quiet")),
                )

    def _on_failed(self, summary: str, details: str) -> None:
        record = self._record
        if not record:
            return
        self._finalize(record)
        callback = record.get("on_error")
        if callback is not None:
            try:
                callback(summary)
            except Exception:
                pass
        self.error.emit(
            record.get("title", "작업"),
            summary,
            details,
            bool(record.get("quiet")),
        )

    def _on_cancelled(self) -> None:
        record = self._record
        if not record:
            return
        self._finalize(record)
        self.message.emit("작업을 취소했습니다. 일부 데이터는 이미 갱신되었을 수 있습니다.", "info")

    def _on_done(self, task: BackgroundTask) -> None:
        # Finalization happens on finished/failed/cancelled.  The done signal
        # only guarantees the worker has fully unwound, so callbacks may safely
        # start a follow-up task.
        if self._record is not None and self._record.get("task") is not task:
            return


def task_logo_pixmap():
    """Convenience for dialogs that want the refresh glyph."""
    return pixmap("refresh", COLORS["teal"], 20)
