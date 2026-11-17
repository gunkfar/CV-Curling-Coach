"""Image <-> ice coordinate mapping.

Consumes a CameraCalibration only; never depends on how it was estimated.
With a lens model: raw px -> undistorted px (cv2.undistortPoints) -> ice (H^-1), and back.
"""

import cv2
import numpy as np

from .lens import distort_pixels, undistort_pixels, within_invertible_range
from .model import CameraCalibration


def _as_points(pts) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 2)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"Expected points with shape (N, 2), got {pts.shape}")
    return pts


class IcePlaneMapper:
    """Maps pixel coordinates to ice-plane coordinates (meters) and back.

    Pixel inputs can be any image location (e.g. bounding-box centers today,
    a better stone localizer later).
    """

    def __init__(self, cal: CameraCalibration):
        self.cal = cal
        self.lens = cal.lens if cal.lens is not None and cal.lens.has_distortion() else None
        self.H = np.asarray(cal.H_ice_to_image, dtype=np.float64)
        self.H_inv = np.linalg.inv(self.H)
        self._region = None
        if cal.valid_region_m is not None:
            self._region = np.asarray(cal.valid_region_m, dtype=np.float32).reshape(-1, 1, 2)

    def image_to_ice(self, pts_px, height_m: float = 0.0) -> np.ndarray:
        """(N, 2) pixel coords -> (N, 2) ice coords in meters, for points at height_m above the ice."""
        if height_m != 0.0:
            if self.cal.pose is None:
                raise ValueError(
                    "Mapping points above the ice needs a metric camera pose, which this calibration "
                    "does not have. Use height_m=0 and treat the result as the ice-plane projection.")
            raise NotImplementedError("Elevated-point mapping is not implemented yet")
        pts = _as_points(pts_px)
        if self.lens is not None:
            pts = undistort_pixels(pts, self.lens)
        return cv2.perspectiveTransform(pts.reshape(-1, 1, 2), self.H_inv).reshape(-1, 2)

    def ice_to_image(self, pts_m) -> np.ndarray:
        """(N, 2) ice coords in meters -> (N, 2) pixel coords."""
        pts = _as_points(pts_m)
        und = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), self.H).reshape(-1, 2)
        return und if self.lens is None else distort_pixels(und, self.lens)

    def ice_in_view(self, pts_m, image_size=None, margin_px: float = 0.0) -> np.ndarray:
        """True where an ice point projects onto a real pixel of the camera image.

        Needs the point in front of the camera, inside the lens model's invertible range and
        inside the image: with margin_px = 0, all four bilinear-sampling neighbours exist. A positive
        margin also accepts points that far outside the image. `image_size` is (width, height) and
        defaults to the calibration's.
        """
        pts = _as_points(pts_m)
        w, h = image_size if image_size is not None else self.cal.image_size
        denom = pts[:, 0] * self.H[2, 0] + pts[:, 1] * self.H[2, 1] + self.H[2, 2]
        ok = denom * self.H[2, 2] > 1e-9          # same side of the horizon as the tee
        und = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), self.H).reshape(-1, 2)
        if self.lens is not None:
            ok &= within_invertible_range(und, self.lens)
            und = distort_pixels(und, self.lens)
        m = margin_px
        return (ok & (und[:, 0] >= -m) & (und[:, 0] <= w - 1 + m)
                & (und[:, 1] >= -m) & (und[:, 1] <= h - 1 + m))

    def in_valid_region(self, pts_m) -> np.ndarray:
        """True where ice points lie inside (or on) the calibration's supported region.

        All True when the calibration does not define a region.
        """
        pts = _as_points(pts_m)
        if self._region is None:
            return np.ones(len(pts), dtype=bool)
        return np.array([cv2.pointPolygonTest(self._region, (float(x), float(y)), False) >= 0
                         for x, y in pts])
