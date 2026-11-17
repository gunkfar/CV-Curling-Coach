"""Tests of cv.camera_calibration_v2.render (render_topdown / render_batch)."""
import inspect
import unittest
from pathlib import Path

import cv2
import numpy as np

import cv.camera_calibration_v2 as cc
from cv.camera_calibration_v2 import render_batch, render_topdown

IMG_DIR = Path(__file__).resolve().parents[2] / "testing/downloaded_images"


def frame(cam, k=0):
    files = sorted(IMG_DIR.glob(f"camera{cam}_*.jpg"))
    if len(files) > k:
        im = cv2.imread(str(files[k]))
        if im is not None:
            return im
    return (np.random.default_rng(cam * 10 + k).random((1024, 1280, 3)) * 255).astype(np.uint8)


class RenderTests(unittest.TestCase):
    def test_defaults_and_signatures(self):
        self.assertEqual(inspect.signature(render_topdown).parameters["view"].default, "wide")
        self.assertEqual(inspect.signature(render_batch).parameters["view"].default, "wide")

    def test_matches_existing_topdown_for_all_12_cameras_and_both_views(self):
        for cam in range(1, 13):
            im, cal = frame(cam), cc.load_camera(f"camera{cam}")
            np.testing.assert_array_equal(render_topdown(im, cam), cc.topdown(cal, im, "wide")[0], err_msg=str(cam))
            self.assertEqual(render_topdown(im, cam).shape, (624, 1140, 3))
            np.testing.assert_array_equal(render_topdown(im, cam, view="house"), cc.topdown(cal, im, "house")[0])
            self.assertEqual(render_topdown(im, cam, "house").shape, (1000, 1000, 3))

    def test_batch_equals_repeated_single_calls_in_order(self):
        ims = [frame(6, 0), frame(6, 1), frame(6, 2)]
        for view in ("wide", "house"):
            out = render_batch(ims, camera_id=6, view=view)
            self.assertEqual(len(out), 3)
            for o, im in zip(out, ims):
                np.testing.assert_array_equal(o, render_topdown(im, 6, view))
        self.assertFalse(np.array_equal(out[0], out[1]))                       # order is meaningful
        np.testing.assert_array_equal(render_batch(ims, 6)[0], render_topdown(ims[0], 6))     # default wide

    def test_empty_batch(self):
        self.assertEqual(render_batch([], camera_id=3), [])

    def test_inputs_not_modified_and_outputs_are_new(self):
        im = frame(1)
        before = im.copy()
        out = render_topdown(im, 1)
        render_batch([im], 1, "house")
        np.testing.assert_array_equal(im, before)
        self.assertFalse(np.shares_memory(out, im))

    def test_clear_errors(self):
        im = frame(1)
        for bad in (0, 13, "1", 1.0, None, True):
            with self.assertRaisesRegex(ValueError, "camera_id"):
                render_topdown(im, bad)
            with self.assertRaisesRegex(ValueError, "camera_id"):
                render_batch([im], bad)
        for bad in ("full", "", None, 3):
            with self.assertRaisesRegex(ValueError, "view"):
                render_topdown(im, 1, bad)
            with self.assertRaisesRegex(ValueError, "view"):
                render_batch([], 1, bad)
        for bad in (None, "x.jpg", np.zeros(0), []):
            with self.assertRaisesRegex(ValueError, "image"):
                render_topdown(bad, 1)
        with self.assertRaisesRegex(ValueError, r"images\[1\]"):
            render_batch([im, "x.jpg"], 1)


if __name__ == "__main__":
    unittest.main()
