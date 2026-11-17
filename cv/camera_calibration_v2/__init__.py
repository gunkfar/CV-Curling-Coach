"""Camera calibration runtime v2: saved v2 HOG 1.422 calibrations (k1 + k2 + cy lens, pixel aspect 1.422) -> image <-> ice coordinates and top-down images.

Standalone copy of the transformation half of cv/calibration_w_hogline_v2 (model, lens, io, transform, rectify, sheet) with the runtime entry
modules (cameras, views, CLI) of camera_calibration; no fitting, annotation or validation tools. Every bundled calibration is an UNVERIFIED candidate; see README.md.
"""

from .cameras import CALIBRATIONS_DIR, describe, list_calibrations, load_camera
from .io import CalibrationStore, camera_id_from_key, load_calibration, save_calibration
from .model import CameraCalibration, IcePose, LensModel, ParamStatus
from .render import render_batch, render_topdown
from .rectify import topdown_coverage, topdown_image, undistorted_image
from .sheet import SheetSpec
from .transform import IcePlaneMapper
from .views import VIEWS, View, coverage, get_view, topdown

__all__ = [
    "CALIBRATIONS_DIR", "CalibrationStore", "CameraCalibration", "IcePlaneMapper", "IcePose", "LensModel",
    "ParamStatus", "SheetSpec", "VIEWS", "View", "camera_id_from_key", "coverage", "describe", "get_view",
    "list_calibrations", "load_calibration", "load_camera", "render_batch", "render_topdown", "save_calibration", "topdown", "topdown_coverage",
    "topdown_image", "undistorted_image",
]
