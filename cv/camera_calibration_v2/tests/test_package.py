"""Verification of camera_calibration_v2: the 12 bundled profiles, their checksums, the v2 lens model, the transforms and the top-down rectification.

All checks are self-contained (the package needs nothing outside its own folder). Run from the repository root:  python -m unittest discover -s cv/camera_calibration_v2/tests -t ."""

import ast
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

import cv.camera_calibration_v2 as cc
from cv.camera_calibration_v2.cameras import CALIBRATIONS_DIR

PKG = Path(cc.__file__).resolve().parent
REPO = PKG.parents[1]        # repository root (the package lives in cv/camera_calibration_v2)
CAMS = [f"camera{i}" for i in range(1, 13)]
HOUSE_LEFT = ("camera1", "camera2", "camera3", "camera4")          # back line at the image LEFT: +X points to image left
HOUSE_RIGHT = ("camera7", "camera9", "camera10", "camera11", "camera12")


def sample_pixels(w=1280, h=1024):
    u, v = np.meshgrid(np.linspace(5, w - 6, 13), np.linspace(5, h - 6, 11))
    return np.column_stack([u.ravel(), v.ravel()])


class BundledProfiles(unittest.TestCase):
    def test_twelve_profiles_present_and_listed(self):
        self.assertEqual(sorted(cc.list_calibrations()), sorted(CAMS))

    def test_checksums_match_the_recorded_sums(self):
        sums = dict(line.split(" *")[::-1] for line in (CALIBRATIONS_DIR / "SHA256SUMS.txt").read_text().split("\n") if line)
        self.assertEqual(sorted(sums), sorted(f"{c}.json" for c in CAMS))
        for name, h in sums.items():
            self.assertEqual(hashlib.sha256((CALIBRATIONS_DIR / name).read_bytes()).hexdigest(), h, name)

    def test_every_profile_is_the_v2_k1_k2_cy_model_at_aspect_1422(self):
        for cam in CAMS:
            cal = cc.load_camera(cam)
            d = json.loads((CALIBRATIONS_DIR / f"{cam}.json").read_text())
            self.assertEqual(d["schema_version"], 2, cam)
            self.assertEqual(d["lens"]["distortion_model"], "radial_k1_k2_cy", cam)
            self.assertEqual(cal.camera_id, cam)
            self.assertAlmostEqual(cc_aspect(cal), 1.422, places=9, msg=cam)
            self.assertEqual(tuple(cal.image_size), (1280, 1024))
            self.assertTrue(cal.lens.has_distortion())
            self.assertNotEqual(float(cal.lens.dist[1]), 0.0, cam)        # k2 present
            self.assertFalse(cal.provenance.get("verified"), cam)

    def test_camera9_is_the_manual_refit_and_camera3_camera10_are_the_originals(self):
        self.assertIn("manual", json.loads((CALIBRATIONS_DIR / "camera9.json").read_text())["provenance"]["pixel_aspect"]["source"])
        for cam in ("camera3", "camera10"):
            self.assertNotIn("manual", json.dumps(json.loads((CALIBRATIONS_DIR / f"{cam}.json").read_text())["provenance"]["pixel_aspect"]))

    def test_describe_and_unknown_camera(self):
        self.assertIn("k2=", cc.describe(cc.load_camera("camera1")))
        with self.assertRaises(FileNotFoundError):
            cc.load_camera("camera13")


def cc_aspect(cal):
    K = np.asarray(cal.lens.K)
    return float(K[1, 1] / K[0, 0])


class Transforms(unittest.TestCase):
    def test_round_trip_every_camera(self):
        for cam in CAMS:
            mp = cc.IcePlaneMapper(cc.load_camera(cam))
            px = sample_pixels()
            np.testing.assert_allclose(mp.ice_to_image(mp.image_to_ice(px)), px, atol=1e-6, err_msg=cam)
            gx, gy = np.meshgrid(np.linspace(-6.0, 1.8, 12), np.linspace(-2.0, 2.0, 7))
            ice = np.column_stack([gx.ravel(), gy.ravel()])
            ok = mp.ice_in_view(ice)
            self.assertGreater(ok.sum(), 20, cam)
            np.testing.assert_allclose(mp.image_to_ice(mp.ice_to_image(ice[ok])), ice[ok], atol=1e-8, err_msg=cam)

    def test_orientation_house_left_and_house_right(self):
        for cam in HOUSE_LEFT + HOUSE_RIGHT:
            mp = cc.IcePlaneMapper(cc.load_camera(cam))
            tee, back, hog = mp.ice_to_image(np.array([[0.0, 0.0], [1.0, 0.0], [-3.0, 0.0]]))
            if cam in HOUSE_LEFT:
                self.assertLess(back[0], tee[0], cam)       # +X (toward the back line) = image left
                self.assertGreater(hog[0], tee[0], cam)
            else:
                self.assertGreater(back[0], tee[0], cam)
                self.assertLess(hog[0], tee[0], cam)
            up = mp.ice_to_image(np.array([[0.0, 1.0]]))[0]  # +Y: image down for house-left, image up for house-right
            self.assertEqual(up[1] > tee[1], cam in HOUSE_LEFT, cam)

    def test_height_not_supported_without_pose(self):
        with self.assertRaises(ValueError):
            cc.IcePlaneMapper(cc.load_camera("camera1")).image_to_ice(np.array([[600.0, 500.0]]), height_m=0.1)


class Topdown(unittest.TestCase):
    def test_house_and_wide_views_shape_and_content(self):
        img = (np.random.default_rng(3).random((1024, 1280, 3)) * 255).astype(np.uint8)
        for cam in CAMS:
            cal = cc.load_camera(cam)
            for view, shape in (("house", (1000, 1000)), ("wide", (624, 1140))):
                out, A = cc.topdown(cal, img, view)
                self.assertEqual(out.shape[:2], shape, (cam, view))
                self.assertGreater(int((out.sum(axis=2) > 0).sum()), 0.2 * shape[0] * shape[1], (cam, view))
                cov = cc.coverage(cal, view)
                self.assertEqual(cov.shape, shape)


class Independence(unittest.TestCase):
    def test_no_absolute_or_original_directory_references_in_code(self):
        for p in PKG.glob("*.py"):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):          # drop docstrings (they may mention the original project by name); comments are not in the AST
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                        and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
                    node.body[0].value.value = ""
            code = ast.unparse(tree)
            self.assertNotRegex(code, r"cv[./\\]calibration|calibration_data|[A-Za-z]:[\\/]", p.name)
            self.assertNotRegex(code, r"(from|import)\s+(cv\.(?!camera_calibration_v2)|camera_calibration\b)", p.name)

    def test_works_without_the_original_packages_importable(self):
        code = ("import sys; sys.modules['cv.calibration_versions'] = None; sys.modules['camera_calibration'] = None\n"
                "import numpy as np, cv.camera_calibration_v2 as cc\n"
                "cal = cc.load_camera('camera12'); mp = cc.IcePlaneMapper(cal)\n"
                "print(mp.image_to_ice(np.array([[640.0, 500.0]]))[0].tolist())\n"
                "out, _ = cc.topdown(cal, np.zeros((1024, 1280, 3), np.uint8), 'house'); print(out.shape)")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
