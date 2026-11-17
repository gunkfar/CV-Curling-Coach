"""Calibration data model, independent of how a calibration was produced.

The ice-plane homography is the one transform every calibration must provide.
A lens model and a metric camera pose are optional: image-only calibration
cannot always determine them, and future methods (e.g. physical targets) can
fill them in without changes to the transformation code.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from .sheet import SheetSpec

# calibration_w_hogline_v2: files holding the extended lens model (k1 + k2 + vertical distortion centre cy) are written
# with SCHEMA_VERSION 2. The original packages (cv.calibration, cv.calibration_w_hogline, camera_calibration) accept only
# version 1 and therefore REJECT such files instead of silently applying a different lens. Calibrations that use exactly the
# legacy model (k1 only, principal point at the image centre) are still written as version 1, so they stay interoperable.
SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1, 2)

# Lens distortion models (LensModel.distortion_model). Both use OpenCV's pinhole model: K = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
# fy = pixel_aspect * fx, dist = [k1, k2, p1, p2, k3] with p1 = p2 = k3 = 0, normalised x = (u - cx) / fx, y = (v - cy) / fy,
# x_d = x (1 + k1 r^2 + k2 r^4). The SAME K and dist are used for undistortion (cv2.undistortPoints), distortion
# (cv2.projectPoints) and image rectification (cv2.undistort / cv2.remap through IcePlaneMapper).
DISTORTION_RADIAL_K1 = "radial_k1"              # legacy: k1 only, principal point at the image centre
DISTORTION_RADIAL_K1_K2_CY = "radial_k1_k2_cy"  # k1, k2 and the vertical distortion centre cy; cx stays at the image centre
DISTORTION_MODELS = (DISTORTION_RADIAL_K1, DISTORTION_RADIAL_K1_K2_CY)

# Parameter groups whose provenance is tracked in CameraCalibration.status.
STATUS_KEYS = ("ice_homography", "lens_distortion", "focal_length", "principal_point",
               "pixel_aspect", "camera_pose", "camera_height")

# Pixel aspect ratio convention (stored with every calibration that has a lens model).
#   pixel_aspect = fy / fx   (K[1,1] / K[0,0]) = horizontal / vertical pixel pitch
# On a camera looking straight down, one pixel then covers `pixel_aspect` times more ice horizontally than
# vertically, and a circle on the ice is imaged as an ellipse that is `pixel_aspect` times taller than wide.
# The reciprocal fx/fy is NOT what is stored. 1.0 means square pixels.
PIXEL_ASPECT_DEFINITION = ("fy/fx = K[1,1]/K[0,0] = horizontal/vertical pixel pitch; a circle on the ice looks "
                           "pixel_aspect times taller than wide (reciprocal, fx/fy, is not stored)")
# How the stored ratio was obtained: from a known pipeline/sensor ("measured"), from indirect evidence
# ("inferred"), or fixed by convention ("assumed").
PIXEL_ASPECT_BASES = ("measured", "inferred", "assumed")


class ParamStatus(str, Enum):
    ESTIMATED = "estimated"  # determined from data
    WEAK = "weak"            # determined from data but poorly constrained
    ASSUMED = "assumed"      # fixed by convention; not physically meaningful
    UNKNOWN = "unknown"      # not available


@dataclass(frozen=True)
class LensModel:
    """OpenCV pinhole intrinsics and distortion (fx != fy allowed)."""

    K: np.ndarray
    dist: np.ndarray
    model: str = "pinhole"
    distortion_model: str = "radial_k1"   # calibration_w_hogline_v2: one of DISTORTION_MODELS

    def has_distortion(self) -> bool:
        return bool(np.any(np.asarray(self.dist) != 0))


@dataclass(frozen=True)
class IcePose:
    """Metric pose of the ice frame relative to the camera (OpenCV rvec/tvec convention)."""

    rvec: np.ndarray
    tvec: np.ndarray


@dataclass(frozen=True)
class CameraCalibration:
    camera_id: str
    image_size: tuple[int, int]          # (width, height) in pixels
    H_ice_to_image: np.ndarray           # 3x3: ice (X, Y, 1) in meters -> undistorted pixel coords
    status: dict                         # STATUS_KEYS -> ParamStatus
    sheet: SheetSpec = field(default_factory=SheetSpec)
    lens: LensModel | None = None        # None: no distortion model (undistorted == raw pixels)
    pose: IcePose | None = None          # None: elevated-point mapping unavailable
    valid_region_m: np.ndarray | None = None  # (N, 2) ice polygon supported by calibration features
    metrics: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    valid_from: str = ""
    schema_version: int = LEGACY_SCHEMA_VERSION   # the version written is decided by io.required_schema_version
