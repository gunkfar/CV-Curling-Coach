"""Tests of the GUI-independent logic of cv.camera_calibration_v2.training_image_gui (no PySide6 needed).

Everything is written to temporary folders; synthetic 1280x1024 frames are used with the saved calibrations.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from cv.camera_calibration_v2 import render_batch, render_topdown
from cv.camera_calibration_v2.training_image_gui import logic


def synthetic_frame(width=1280, height=1024, seed=0):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    cv2.circle(img, (width // 2, height // 2), 200, (0, 0, 255), 6)
    return img


def write_image(path, img, ext=None):
    ok, buf = cv2.imencode(ext or Path(path).suffix, img)
    assert ok
    Path(path).write_bytes(buf.tobytes())
    return Path(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.src = self.tmp / "in"
        self.out = self.tmp / "out"
        self.src.mkdir()
        self.out.mkdir()


class Validation(TempDirCase):
    def test_accepts_valid_jpg_and_png_of_expected_size(self):
        a = write_image(self.src / "camera6_a.jpg", synthetic_frame())
        b = write_image(self.src / "camera6_b.PNG", synthetic_frame(seed=1))
        sel = logic.ImageSelection()
        res = sel.add([a, b])
        self.assertEqual([i.name for i in res.added], ["camera6_a.jpg", "camera6_b.PNG"])
        self.assertFalse(res.rejected or res.duplicates)
        self.assertEqual((sel.items[0].width, sel.items[0].height), (1280, 1024))
        self.assertEqual(res.warning_text(), "")

    def test_rejects_wrong_dimensions_with_reason_and_keeps_other_files(self):
        bad = write_image(self.src / "camera6_example.jpg", synthetic_frame(1920, 1080))
        good = write_image(self.src / "camera6_ok.jpg", synthetic_frame())
        sel = logic.ImageSelection()
        res = sel.add([bad, good])
        self.assertEqual(len(sel), 1)
        self.assertEqual(sel.items[0].name, "camera6_ok.jpg")
        self.assertIn("camera6_example.jpg was rejected: expected 1280 × 1024 pixels, received 1920 × 1080.", res.warning_text())

    def test_rejects_unreadable_corrupt_unsupported_empty_missing_and_folders(self):
        corrupt = self.src / "camera6_corrupt.jpg"
        corrupt.write_bytes(b"this is not a jpeg")
        empty = self.src / "camera6_empty.png"
        empty.write_bytes(b"")
        bmp = write_image(self.src / "camera6_x.bmp", synthetic_frame())
        folder = self.src / "folder.jpg"
        folder.mkdir()
        missing = self.src / "camera6_missing.jpg"
        sel = logic.ImageSelection()
        res = sel.add([corrupt, empty, bmp, folder, missing])
        self.assertEqual(len(sel), 0)
        self.assertEqual(len(res.rejected), 5)
        reasons = {p.name: r for p, r in res.rejected}
        self.assertIn("could not be decoded", reasons["camera6_corrupt.jpg"])
        self.assertIn("empty", reasons["camera6_empty.png"])
        self.assertIn("unsupported file type '.bmp'", reasons["camera6_x.bmp"])
        self.assertIn("folder", reasons["folder.jpg"])
        self.assertIn("could not be read", reasons["camera6_missing.jpg"])

    def test_duplicates_are_detected_by_path_not_name(self):
        a = write_image(self.src / "camera6_a.jpg", synthetic_frame())
        sub = self.src / "sub"
        sub.mkdir()
        same_name_other_file = write_image(sub / "camera6_a.jpg", synthetic_frame(seed=3))
        sel = logic.ImageSelection()
        sel.add([a])
        res = sel.add([a, self.src / "sub" / ".." / "camera6_a.jpg", same_name_other_file, same_name_other_file])
        self.assertEqual(len(sel), 2)                                           # the same-named file in another folder is a different file
        self.assertEqual(len(res.duplicates), 3)                                # a again, a via '..', and the second copy of the other file
        self.assertIn("already in the list", res.warning_text())

    def test_spaces_and_unicode_in_paths(self):
        folder = self.src / "Ünïcode folder 日本"
        folder.mkdir()
        p = write_image(folder / "camera6 ümlaut 画像.png", synthetic_frame())
        sel = logic.ImageSelection()
        self.assertEqual(len(sel.add([p]).added), 1)
        res = logic.run_batch(sel.paths(), 6, "wide", self.out)
        self.assertEqual(res.succeeded, 1)
        self.assertEqual(logic.read_image(res.results[0].output).shape[:2], (624, 1140))

    def test_remove_and_clear(self):
        paths = [write_image(self.src / f"camera6_{i}.jpg", synthetic_frame(seed=i)) for i in range(3)]
        sel = logic.ImageSelection()
        sel.add(paths)
        sel.remove([0, 2])
        self.assertEqual([i.name for i in sel.items], ["camera6_1.jpg"])
        sel.add(paths)                                                          # re-adding what was removed works
        self.assertEqual(len(sel), 3)
        sel.clear()
        self.assertEqual(len(sel), 0)

    def test_decoding_matches_cv2_imread(self):
        p = write_image(self.src / "camera6_a.jpg", synthetic_frame())
        self.assertTrue(np.array_equal(logic.read_image(p), cv2.imread(str(p))))


class CameraSelection(unittest.TestCase):
    def test_loads_each_saved_calibration(self):
        for cam in logic.CAMERA_IDS:
            cal = logic.load_calibration_for(cam)
            self.assertEqual(cal.camera_id, f"camera{cam}")
            self.assertTrue(logic.calibration_warning(cal).startswith(f"camera{cam} calibration is UNVERIFIED"))

    def test_invalid_camera_id(self):
        for bad in (0, 13, True, "6"):
            with self.assertRaises(ValueError):
                logic.camera_name(bad)

    def test_unloadable_calibration_gives_informative_error(self):
        from unittest import mock
        with mock.patch.object(logic, "load_camera", side_effect=FileNotFoundError("missing json")):
            with self.assertRaisesRegex(logic.CalibrationUnavailable, "camera6 could not be loaded.*missing json"):
                logic.load_calibration_for(6)

    def test_filename_camera_mismatch(self):
        names = ["camera6_20260519_1.jpg", "camera7_20260519_2.jpg", "photo.jpg", "camera10_x.png"]
        self.assertEqual(logic.filename_camera_mismatches(names, 6), [("camera7_20260519_2.jpg", "camera7"), ("camera10_x.png", "camera10")])
        self.assertEqual(logic.filename_camera_mismatches(["camera1_a.jpg"], 1), [])

    def test_views(self):
        self.assertEqual(logic.VIEW_NAMES[0], "wide")
        self.assertEqual(set(logic.VIEW_NAMES), {"wide", "house"})


class OutputDirectory(TempDirCase):
    def test_states(self):
        f = self.tmp / "afile.txt"
        f.write_text("x")
        self.assertIs(logic.output_dir_state(""), logic.DirState.EMPTY)
        self.assertIs(logic.output_dir_state("   "), logic.DirState.EMPTY)
        self.assertIs(logic.output_dir_state(self.out), logic.DirState.OK)
        self.assertIs(logic.output_dir_state(self.tmp / "nope"), logic.DirState.MISSING)
        self.assertIs(logic.output_dir_state(f), logic.DirState.NOT_A_DIRECTORY)

    def test_ensure_creates_only_when_missing_and_rejects_files(self):
        new = self.tmp / "a" / "b"
        self.assertEqual(logic.ensure_output_dir(str(new)), new)
        self.assertTrue(new.is_dir())
        f = self.tmp / "afile.txt"
        f.write_text("x")
        with self.assertRaises(logic.OutputDirError):
            logic.ensure_output_dir(f)
        with self.assertRaises(logic.OutputDirError):
            logic.ensure_output_dir("")

    def test_run_batch_requires_existing_folder(self):
        with self.assertRaises(logic.OutputDirError):
            logic.run_batch([], 6, "wide", self.tmp / "missing")

    def test_output_name(self):
        self.assertEqual(logic.output_name("x/camera6_20260519_154543.jpg", 6, "wide"), "camera6_20260519_154543_camera6_wide.png")


class Batch(TempDirCase):
    def _sources(self, n=3):
        return [write_image(self.src / f"camera6_2026_{i}.jpg", synthetic_frame(seed=i)) for i in range(n)]

    def test_output_sizes_and_equivalence_with_render_functions(self):
        sources = self._sources(3)
        for view, size in (("wide", (624, 1140)), ("house", (1000, 1000))):
            out = self.out / view
            out.mkdir()
            seen = []
            summary = logic.run_batch(sources, 6, view, out, on_progress=lambda d, t, r: seen.append((d, t)))
            self.assertEqual((summary.succeeded, summary.failed, summary.skipped), (3, 0, 0))
            self.assertEqual(seen, [(1, 3), (2, 3), (3, 3)])
            frames = [logic.read_image(s) for s in sources]
            expected = render_batch(frames, 6, view)
            for src, res, exp in zip(sources, summary.results, expected):
                got = logic.read_image(res.output)
                self.assertEqual(got.shape[:2], size)
                self.assertEqual(res.output.name, f"{src.stem}_camera6_{view}.png")
                self.assertTrue(np.array_equal(got, exp))                       # PNG is lossless: identical to the existing renderer
            self.assertTrue(np.array_equal(logic.read_image(summary.results[0].output), render_topdown(frames[0], 6, view)))

    def test_other_cameras_use_their_own_calibration(self):
        p = write_image(self.src / "camera9_a.jpg", synthetic_frame())
        res = logic.run_batch([p], 9, "wide", self.out)
        self.assertEqual(res.results[0].output.name, "camera9_a_camera9_wide.png")
        self.assertTrue(np.array_equal(logic.read_image(res.results[0].output), render_topdown(logic.read_image(p), 9, "wide")))

    def test_inputs_are_preserved(self):
        sources = self._sources(2)
        before = {s: (sha(s), s.stat().st_mtime_ns) for s in sources}
        before_names = sorted(p.name for p in self.src.iterdir())
        logic.run_batch(sources, 6, "wide", self.out)
        self.assertEqual(before, {s: (sha(s), s.stat().st_mtime_ns) for s in sources})
        self.assertEqual(before_names, sorted(p.name for p in self.src.iterdir()))

    def test_existing_outputs_are_never_overwritten(self):
        sources = self._sources(2)
        existing = self.out / logic.output_name(sources[0], 6, "wide")
        existing.write_bytes(b"precious")
        summary = logic.run_batch(sources, 6, "wide", self.out)
        self.assertEqual((summary.succeeded, summary.failed, summary.skipped), (1, 0, 1))
        self.assertEqual(summary.results[0].status, logic.SKIPPED)
        self.assertIn("already exists", summary.results[0].message)
        self.assertEqual(existing.read_bytes(), b"precious")
        again = logic.run_batch(sources, 6, "wide", self.out)                  # a second run skips everything
        self.assertEqual((again.succeeded, again.skipped), (0, 2))

    def test_exclusive_write_refuses_existing_file_even_if_it_appears_late(self):
        target = self.out / "x.png"
        target.write_bytes(b"old")
        with self.assertRaises(FileExistsError):
            logic.write_png_exclusive(synthetic_frame(8, 8), target)
        self.assertEqual(target.read_bytes(), b"old")

    def test_same_stem_from_two_folders_collides_safely(self):
        other = self.src / "other"
        other.mkdir()
        a = write_image(self.src / "camera6_same.jpg", synthetic_frame())
        b = write_image(other / "camera6_same.jpg", synthetic_frame(seed=9))
        summary = logic.run_batch([a, b], 6, "wide", self.out)
        self.assertEqual((summary.succeeded, summary.skipped), (1, 1))
        self.assertTrue(np.array_equal(logic.read_image(summary.results[0].output),
                                       render_topdown(logic.read_image(a), 6, "wide")))

    def test_one_failing_image_does_not_abort_the_batch(self):
        sources = self._sources(3)
        sources[1].write_bytes(b"garbage after validation")                     # became unreadable between adding and processing
        wrong_size = write_image(self.src / "camera6_small.png", synthetic_frame(640, 480))
        missing = self.src / "camera6_gone.jpg"
        summary = logic.run_batch([sources[0], sources[1], wrong_size, missing, sources[2]], 6, "wide", self.out)
        self.assertEqual([r.status for r in summary.results], [logic.OK, logic.FAILED, logic.FAILED, logic.FAILED, logic.OK])
        self.assertIn("could not be decoded", summary.results[1].message)
        self.assertIn("expected 1280 × 1024 pixels, received 640 × 480", summary.results[2].message)
        self.assertEqual(len(list(self.out.glob("*.png"))), 2)
        self.assertIn("2 succeeded, 3 failed, 0 skipped", summary.text())

    def test_render_failure_is_recorded_and_the_batch_continues(self):
        from unittest import mock
        sources = self._sources(3)
        real = logic.render_image
        calls = []

        def flaky(cal, image, view):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("boom")
            return real(cal, image, view)

        with mock.patch.object(logic, "render_image", flaky):
            summary = logic.run_batch(sources, 6, "wide", self.out)
        self.assertEqual((summary.succeeded, summary.failed), (2, 1))
        self.assertEqual(summary.results[1].message, "RuntimeError: boom")
        self.assertEqual(len(list(self.out.glob("*.png"))), 2)                 # no partial file for the failed image

    def test_cancel_takes_effect_between_images(self):
        sources = self._sources(4)
        done = []
        summary = logic.run_batch(sources, 6, "wide", self.out, on_progress=lambda d, t, r: done.append(d),
                                  should_cancel=lambda: len(done) >= 2)
        self.assertTrue(summary.cancelled)
        self.assertEqual((summary.succeeded, summary.not_processed), (2, 2))
        self.assertEqual(len(list(self.out.glob("*.png"))), 2)

    def test_calibration_is_loaded_once_per_batch(self):
        from unittest import mock
        sources = self._sources(3)
        with mock.patch.object(logic, "load_camera", wraps=logic.load_camera) as m:
            logic.run_batch(sources, 6, "wide", self.out)
        self.assertEqual(m.call_count, 1)

    def test_preview_matches_batch_output_and_saves_nothing(self):
        p = self._sources(1)[0]
        preview = logic.render_preview(p, 6, "house")
        self.assertEqual(preview.shape[:2], (1000, 1000))
        self.assertEqual(list(self.out.iterdir()), [])
        res = logic.run_batch([p], 6, "house", self.out)
        self.assertTrue(np.array_equal(preview, logic.read_image(res.results[0].output)))
        with self.assertRaises(logic.ImageRejected):
            logic.render_preview(write_image(self.src / "small.png", synthetic_frame(100, 100)), 6, "wide")


if __name__ == "__main__":
    unittest.main()
