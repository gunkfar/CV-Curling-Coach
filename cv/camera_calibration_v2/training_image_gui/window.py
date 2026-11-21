"""PySide6 window of the training-image tool. All decisions and image work live in logic.py; this file only wires widgets to it."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import logic


class BatchWorker(QThread):
    """Runs logic.run_batch off the GUI thread. Cancellation (requestInterruption) takes effect between images only."""

    progress = Signal(int, int, object)          # done, total, logic.ItemResult
    batchDone = Signal(object)                   # logic.BatchSummary
    batchError = Signal(str)

    def __init__(self, paths, camera_id, view, out_dir, cal, parent=None):
        super().__init__(parent)
        self._args = (paths, camera_id, view, out_dir)
        self._cal = cal

    def run(self):
        paths, camera_id, view, out_dir = self._args
        try:
            summary = logic.run_batch(paths, camera_id, view, out_dir, cal=self._cal,
                                      on_progress=lambda done, total, result: self.progress.emit(done, total, result),
                                      should_cancel=self.isInterruptionRequested)
        except Exception as e:                                                  # e.g. output folder vanished
            self.batchError.emit(f"{type(e).__name__}: {e}")
            return
        self.batchDone.emit(summary)


class PreviewLabel(QLabel):
    """Shows a pixmap scaled to fit (aspect ratio kept) or a plain message."""

    def __init__(self):
        super().__init__()
        self._pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumSize(360, 220)
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def show_message(self, text):
        self._pixmap = None
        self.setPixmap(QPixmap())
        self.setText(text)

    def show_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.setText("")
        self._rescale()

    def _rescale(self):
        if self._pixmap is not None:
            self.setPixmap(self._pixmap.scaled(self.contentsRect().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


def to_pixmap(bgr: np.ndarray) -> QPixmap:
    bgr = np.ascontiguousarray(bgr)
    h, w = bgr.shape[:2]
    return QPixmap.fromImage(QImage(bgr.data, w, h, bgr.strides[0], QImage.Format_BGR888).copy())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Training Image Transformer")
        self.resize(1080, 760)
        self.setAcceptDrops(True)
        self.selection = logic.ImageSelection()
        self._worker = None
        self._summary = None
        self._calibration = None                 # calibration of the selected camera, None if none chosen / not loadable
        self._last_input_dir = str(Path.home())
        self._build()
        self._update_state()

    # ------------------------------------------------------------------------------------------------------------------------- layout
    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        top = QHBoxLayout()
        top.addWidget(QLabel("Camera"))
        self.camera_combo = QComboBox()
        self.camera_combo.addItems([logic.camera_name(i) for i in logic.CAMERA_IDS])
        self.camera_combo.setPlaceholderText("Choose camera…")
        self.camera_combo.setCurrentIndex(-1)
        top.addWidget(self.camera_combo)
        top.addSpacing(20)
        top.addWidget(QLabel("Output View"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(list(logic.VIEW_NAMES))             # "wide" first = default
        top.addWidget(self.view_combo)
        top.addStretch(1)
        outer.addLayout(top)
        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)

        middle = QHBoxLayout()
        outer.addLayout(middle, 1)

        left = QVBoxLayout()
        middle.addLayout(left, 3)
        self.drop_label = QLabel("Drag and drop images here\n(JPG, JPEG or PNG, exactly 1280 × 1024)")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setMinimumHeight(64)
        self.drop_label.setStyleSheet("QLabel { border: 2px dashed palette(mid); border-radius: 6px; }")
        left.addWidget(self.drop_label)
        row = QHBoxLayout()
        self.add_button = QPushButton("Add Images…")
        self.remove_button = QPushButton("Remove Selected")
        self.clear_button = QPushButton("Clear All")
        for b in (self.add_button, self.remove_button, self.clear_button):
            row.addWidget(b)
        left.addLayout(row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Filename", "Size", "Folder"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        left.addWidget(self.table, 1)
        self.count_label = QLabel("")
        left.addWidget(self.count_label)

        right = QVBoxLayout()
        middle.addLayout(right, 4)
        right.addWidget(QLabel("Preview (top-down view of the selected image; not saved)"))
        self.preview = PreviewLabel()
        right.addWidget(self.preview, 1)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder"))
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Choose where the transformed PNG files are saved")
        out_row.addWidget(self.out_edit, 1)
        self.browse_button = QPushButton("Browse…")
        out_row.addWidget(self.browse_button)
        outer.addLayout(out_row)

        run_row = QHBoxLayout()
        self.transform_button = QPushButton("Transform Images")
        self.transform_button.setMinimumHeight(36)
        font = self.transform_button.font()
        font.setBold(True)
        self.transform_button.setFont(font)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        run_row.addWidget(self.transform_button, 1)
        run_row.addWidget(self.cancel_button)
        outer.addLayout(run_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat(" ")                    # blank until a run starts
        outer.addWidget(self.progress)
        self.status = QLabel("Add images, choose the camera and an output folder.")
        outer.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        outer.addWidget(self.log)

        self.add_button.clicked.connect(self._browse_images)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_all)
        self.browse_button.clicked.connect(self._browse_output)
        self.out_edit.textChanged.connect(self._update_state)
        self.camera_combo.currentIndexChanged.connect(self._camera_changed)
        self.view_combo.currentIndexChanged.connect(self._update_preview)
        self.table.itemSelectionChanged.connect(self._update_preview)
        self.transform_button.clicked.connect(self._start_transform)
        self.cancel_button.clicked.connect(self._cancel)

    # ----------------------------------------------------------------------------------------------------------------------- helpers
    @property
    def busy(self):
        return self._worker is not None

    def _camera_id(self):
        index = self.camera_combo.currentIndex()
        return None if index < 0 else logic.CAMERA_IDS[index]

    def _view(self):
        return self.view_combo.currentText()

    def _update_state(self):
        busy = self.busy
        n = len(self.selection)
        self.count_label.setText(f"{n} image{'s' if n != 1 else ''} selected")
        ready = (n > 0 and self._calibration is not None and bool(self.out_edit.text().strip()) and not busy)
        self.transform_button.setEnabled(ready)
        for w in (self.camera_combo, self.view_combo, self.add_button, self.remove_button, self.clear_button, self.browse_button,
                  self.out_edit, self.table):
            w.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    # ------------------------------------------------------------------------------------------------------------- adding / removing
    def _browse_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select camera images", self._last_input_dir,
                                                "Images (*.jpg *.jpeg *.png);;All files (*)")
        if files:
            self._last_input_dir = str(Path(files[0]).parent)
            self.add_images(files)

    def add_images(self, paths):
        """Both 'Add Images…' and drag-and-drop end up here: the same validation, one consolidated warning."""
        if self.busy:
            return
        result = self.selection.add(paths)
        self._refresh_table()
        text = result.warning_text()
        if text:
            QMessageBox.warning(self, "Some images were not added", text)
        if result.added:
            self.status.setText(f"Added {len(result.added)} image(s).")

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.selection))
        for row, info in enumerate(self.selection.items):
            cells = (info.name, f"{info.width} × {info.height}", str(info.path.parent))
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(str(info.path))
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self._update_state()
        self._update_preview()

    def _remove_selected(self):
        rows = {i.row() for i in self.table.selectionModel().selectedRows()}
        if rows:
            self.selection.remove(rows)
            self._refresh_table()

    def _clear_all(self):
        self.selection.clear()
        self._refresh_table()

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths and not self.busy:
            event.acceptProposedAction()
            self.add_images(paths)

    # ------------------------------------------------------------------------------------------------------------- camera / preview
    def _camera_changed(self):
        self._calibration = None
        self.notice.setText("")
        self.notice.setStyleSheet("")
        camera_id = self._camera_id()
        if camera_id is not None:
            try:
                self._calibration = logic.load_calibration_for(camera_id)
            except logic.CalibrationUnavailable as e:
                self.notice.setStyleSheet("color: #b00020;")
                self.notice.setText(str(e))
                QMessageBox.critical(self, "Calibration not available", str(e))
            else:
                warning = logic.calibration_warning(self._calibration)
                self.notice.setStyleSheet("color: #8a5a00;")
                self.notice.setText(warning)
        self._update_state()
        self._update_preview()

    def _update_preview(self):
        if self.busy:
            return
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        if len(rows) != 1:
            self.preview.show_message("Select one image in the list to preview its top-down view.")
            return
        if self._calibration is None:
            self.preview.show_message("Choose a camera to preview the top-down view.")
            return
        info = self.selection.items[rows[0]]
        try:
            image = logic.render_preview(info.path, self._camera_id(), self._view(), self._calibration)
        except Exception as e:
            self.preview.show_message(f"Preview not available for {info.name}:\n{e}")
            return
        self.preview.show_pixmap(to_pixmap(image))

    # --------------------------------------------------------------------------------------------------------------------- output dir
    def _browse_output(self):
        start = self.out_edit.text().strip() or self._last_input_dir
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", start)
        if folder:
            self.out_edit.setText(folder)

    # ---------------------------------------------------------------------------------------------------------------------- transform
    def _start_transform(self):
        camera_id = self._camera_id()
        if self.busy or camera_id is None or not len(self.selection):
            return
        paths = self.selection.paths()

        mismatches = logic.filename_camera_mismatches(paths, camera_id)
        if mismatches:
            lines = [f"{name} (file name says {named})" for name, named in mismatches[:logic.MAX_LISTED]]
            if len(mismatches) > logic.MAX_LISTED:
                lines.append(f"... and {len(mismatches) - logic.MAX_LISTED} more")
            box = QMessageBox(QMessageBox.Warning, "Camera does not match file names",
                              f"{logic.camera_name(camera_id)} is selected, but these file names name a different camera:\n\n"
                              + "\n".join(lines) + "\n\nUsing the wrong camera gives wrong top-down images.", parent=self)
            proceed = box.addButton("Process Anyway", QMessageBox.AcceptRole)
            cancel = box.addButton("Cancel", QMessageBox.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not proceed:
                return

        text = self.out_edit.text().strip()
        state = logic.output_dir_state(text)
        if state is logic.DirState.MISSING:
            answer = QMessageBox.question(self, "Create output folder?", f"The folder\n{text}\ndoes not exist. Create it?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer != QMessageBox.Yes:
                return
        try:
            out_dir = logic.ensure_output_dir(text)
            cal = logic.load_calibration_for(camera_id)
        except (logic.OutputDirError, logic.CalibrationUnavailable) as e:
            QMessageBox.critical(self, "Cannot start", str(e))
            return

        self._summary = None
        self.log.clear()
        self.progress.setRange(0, len(paths))
        self.progress.setFormat("%v / %m")
        self.progress.setValue(0)
        self.status.setText(f"0 / {len(paths)} images processed")
        self.preview.show_message("Transforming…")
        self._worker = BatchWorker(paths, camera_id, self._view(), out_dir, cal, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.batchDone.connect(self._on_done)
        self._worker.batchError.connect(self._on_error)
        self._worker.finished.connect(self._on_thread_finished)
        self._update_state()
        self._worker.start()

    def _cancel(self):
        if self._worker is not None:
            self._worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling after the current image…")

    def _on_progress(self, done, total, result):
        self.progress.setValue(done)
        self.status.setText(f"{done} / {total} images processed")
        label = {logic.OK: "OK     ", logic.FAILED: "FAILED ", logic.SKIPPED: "SKIPPED"}[result.status]
        detail = result.output.name if result.status == logic.OK else result.message
        self.log.appendPlainText(f"{label} {result.source.name}: {detail}")

    def _on_done(self, summary):
        self._summary = summary

    def _on_error(self, message):
        self._summary = message

    def _on_thread_finished(self):
        worker, self._worker = self._worker, None
        worker.deleteLater()
        self._update_state()
        summary, self._summary = self._summary, None
        self._update_preview()
        if isinstance(summary, str):
            self.status.setText("The transformation stopped with an error.")
            QMessageBox.critical(self, "Transformation failed", summary)
        elif summary is not None:
            self.status.setText(("Cancelled. " if summary.cancelled else "Finished. ") + summary.text().splitlines()[0])
            box = QMessageBox.Warning if (summary.failed or summary.cancelled) else QMessageBox.Information
            QMessageBox(box, "Transformation cancelled" if summary.cancelled else "Transformation finished", summary.text(),
                        parent=self).exec()

    def closeEvent(self, event):
        if self.busy:
            answer = QMessageBox.question(self, "Transformation running", "Cancel the running transformation and quit?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.requestInterruption()
            self._worker.wait()                                                # at most the image currently being written
        event.accept()


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(list(argv) if argv is not None else sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
