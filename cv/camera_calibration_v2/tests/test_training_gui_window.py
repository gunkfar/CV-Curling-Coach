"""Smoke tests of the PySide6 window, run with Qt's offscreen platform (skipped when PySide6 is not installed).

All dialogs are replaced by test doubles, so nothing blocks; files are written to temporary folders only.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication, QMessageBox
    from cv.camera_calibration_v2.training_image_gui import logic, window
    HAVE_QT = True
except ImportError:                                       # pragma: no cover
    HAVE_QT = False

from cv.camera_calibration_v2 import render_topdown
from cv.camera_calibration_v2.tests.test_training_gui_logic import synthetic_frame, write_image


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class WindowSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        (self.tmp / "in").mkdir()
        self.srcs = [write_image(self.tmp / "in" / f"camera6_{i}.jpg", synthetic_frame(seed=i)) for i in range(3)]
        self.w = window.MainWindow()
        self.addCleanup(self.w.deleteLater)
        # replace every modal dialog; record what would have been shown
        self.shown = []
        for name in ("warning", "critical", "information"):
            p = mock.patch.object(QMessageBox, name, side_effect=lambda *a, _n=name, **k: self.shown.append((_n, a[2] if len(a) > 2 else "")))
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(QMessageBox, "exec", lambda box: self.shown.append(("summary", box.text())) or 0)
        p.start()
        self.addCleanup(p.stop)

    def wait_idle(self, timeout=60):
        end = time.time() + timeout
        while self.w.busy and time.time() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(self.w.busy)

    def test_initial_state_defaults_and_button_enabling(self):
        w = self.w
        self.assertEqual(w.camera_combo.count(), 12)
        self.assertEqual([w.camera_combo.itemText(i) for i in (0, 11)], ["camera1", "camera12"])
        self.assertEqual(w.camera_combo.currentIndex(), -1)                      # no camera assumed
        self.assertEqual(w.view_combo.currentText(), "wide")
        self.assertEqual([w.view_combo.itemText(i) for i in range(2)], ["wide", "house"])
        self.assertFalse(w.transform_button.isEnabled())
        w.add_images([str(self.srcs[0])])
        self.assertFalse(w.transform_button.isEnabled())                          # still no camera / folder
        w.camera_combo.setCurrentIndex(5)
        self.assertEqual(w._camera_id(), 6)
        self.assertIn("UNVERIFIED", w.notice.text())
        self.assertFalse(w.transform_button.isEnabled())                          # still no folder
        w.out_edit.setText(str(self.tmp / "out"))
        self.assertTrue(w.transform_button.isEnabled())
        w._clear_all()
        self.assertFalse(w.transform_button.isEnabled())

    def test_add_list_remove_clear_and_consolidated_warning(self):
        w = self.w
        bad = write_image(self.tmp / "in" / "camera6_big.jpg", synthetic_frame(1920, 1080))
        corrupt = self.tmp / "in" / "camera6_bad.png"
        corrupt.write_bytes(b"nope")
        w.add_images([str(p) for p in self.srcs] + [str(bad), str(corrupt), str(self.srcs[0])])
        self.assertEqual(w.table.rowCount(), 3)
        self.assertEqual(w.count_label.text(), "3 images selected")
        self.assertEqual(w.table.item(0, 1).text(), "1280 × 1024")
        self.assertEqual(w.table.item(0, 0).toolTip(), str(self.srcs[0].resolve()))
        self.assertEqual(len([s for s in self.shown if s[0] == "warning"]), 1)  # one consolidated warning
        text = self.shown[-1][1]
        self.assertIn("camera6_big.jpg was rejected: expected 1280 × 1024 pixels, received 1920 × 1080.", text)
        self.assertIn("camera6_bad.png was rejected", text)
        self.assertIn("camera6_0.jpg was skipped", text)
        w.table.selectRow(1)
        w._remove_selected()
        self.assertEqual([i.name for i in w.selection.items], ["camera6_0.jpg", "camera6_2.jpg"])
        w.add_images([str(self.srcs[1])])                                         # additions keep the existing selection
        self.assertEqual(w.table.rowCount(), 3)
        w._clear_all()
        self.assertEqual((w.table.rowCount(), w.count_label.text()), (0, "0 images selected"))

    def test_drag_and_drop_uses_the_same_validation(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)) for p in self.srcs[:2]])
        event = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self.w.dropEvent(event)
        self.assertEqual(len(self.w.selection), 2)

    def test_preview_follows_selection_camera_and_view(self):
        w = self.w
        w.add_images([str(self.srcs[0])])
        w.table.selectRow(0)
        self.assertIn("Choose a camera", w.preview.text())
        w.camera_combo.setCurrentIndex(5)
        self.assertIsNotNone(w.preview._pixmap)
        self.assertEqual((w.preview._pixmap.width(), w.preview._pixmap.height()), (1140, 624))
        w.view_combo.setCurrentIndex(1)
        self.assertEqual((w.preview._pixmap.width(), w.preview._pixmap.height()), (1000, 1000))
        w.resize(700, 500)
        w.show()
        self.app.processEvents()
        shown = w.preview.pixmap()
        self.assertLessEqual(shown.width(), w.preview.width())
        self.assertLessEqual(shown.height(), w.preview.height())
        self.assertAlmostEqual(shown.width() / shown.height(), 1.0, delta=0.02)   # aspect ratio preserved
        self.assertEqual(list((self.tmp).glob("out*")), [])                        # nothing saved by previewing
        w.table.clearSelection()
        self.assertIn("Select one image", w.preview.text())

    def test_preview_error_is_shown_in_the_preview_area(self):
        w = self.w
        w.add_images([str(self.srcs[0])])
        w.camera_combo.setCurrentIndex(5)
        self.srcs[0].write_bytes(b"corrupted later")
        w.table.selectRow(0)
        self.assertIn("Preview not available for camera6_0.jpg", w.preview.text())

    def test_transform_end_to_end_with_progress_and_folder_creation(self):
        w = self.w
        w.add_images([str(p) for p in self.srcs])
        w.camera_combo.setCurrentIndex(5)
        out = self.tmp / "new" / "out"
        w.out_edit.setText(str(out))
        progress = []
        w.progress.valueChanged.connect(progress.append)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes) as ask:
            w.transform_button.click()
            self.assertTrue(w.busy)
            self.assertFalse(w.transform_button.isEnabled() or w.add_button.isEnabled() or w.camera_combo.isEnabled())
            self.assertTrue(w.cancel_button.isEnabled())
            self.wait_idle()
        ask.assert_called_once()                                                  # offered to create the missing folder
        files = sorted(p.name for p in out.glob("*.png"))
        self.assertEqual(files, [f"camera6_{i}_camera6_wide.png" for i in range(3)])
        self.assertEqual(progress[-1], 3)
        self.assertEqual(w.status.text(), "Finished. 3 succeeded, 0 failed, 0 skipped")
        self.assertEqual(self.shown[-1][0], "summary")
        self.assertTrue(w.add_button.isEnabled() and w.transform_button.isEnabled())
        for i, s in enumerate(self.srcs):
            got = logic.read_image(out / f"camera6_{i}_camera6_wide.png")
            self.assertTrue(np.array_equal(got, render_topdown(cv2.imread(str(s)), 6, "wide")))
        self.assertIn("OK", w.log.toPlainText())
        # running again skips everything and reports it
        with mock.patch.object(QMessageBox, "question") as ask2:
            w.transform_button.click()
            self.wait_idle()
        ask2.assert_not_called()
        self.assertEqual(w.status.text(), "Finished. 0 succeeded, 0 failed, 3 skipped")

    def test_filename_camera_mismatch_asks_before_processing(self):
        w = self.w
        w.add_images([str(p) for p in self.srcs[:1]])
        w.camera_combo.setCurrentIndex(6)                                         # camera7 selected, file says camera6
        w.out_edit.setText(str(self.tmp / "out"))
        (self.tmp / "out").mkdir()
        with mock.patch.object(QMessageBox, "exec", return_value=0) as shown_box, \
                mock.patch.object(QMessageBox, "clickedButton", return_value=None):          # user does not press "Process Anyway"
            w.transform_button.click()
        shown_box.assert_called_once()                                            # the mismatch warning was displayed
        self.assertFalse(w.busy)
        self.assertEqual(list((self.tmp / "out").iterdir()), [])

    def test_cancel_stops_between_images_without_losing_finished_ones(self):
        w = self.w
        w.add_images([str(p) for p in self.srcs])
        w.camera_combo.setCurrentIndex(5)
        (self.tmp / "out").mkdir()
        w.out_edit.setText(str(self.tmp / "out"))
        w.progress.valueChanged.connect(lambda v: w.cancel_button.click() if v == 1 else None)
        w.transform_button.click()
        self.wait_idle()
        n = len(list((self.tmp / "out").glob("*.png")))
        self.assertTrue(1 <= n < 3, n)
        self.assertTrue(w.status.text().startswith("Cancelled."))

    def test_missing_calibration_shows_error_and_blocks_transform(self):
        w = self.w
        w.add_images([str(self.srcs[0])])
        w.out_edit.setText(str(self.tmp))
        with mock.patch.object(logic, "load_camera", side_effect=FileNotFoundError("no json")):
            w.camera_combo.setCurrentIndex(2)
        self.assertEqual(self.shown[-1][0], "critical")
        self.assertIn("could not be loaded", w.notice.text())
        self.assertFalse(w.transform_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
