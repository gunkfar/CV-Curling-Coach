"""Pixel <-> undistorted-pixel conversion for a LensModel (thin wrappers around OpenCV).

"Undistorted pixels" are the coordinates an ideal pinhole camera with the same
camera matrix K would produce. CameraCalibration.H_ice_to_image maps ice to these.
"""

import cv2
import numpy as np

from .model import LensModel

# cv2.undistortPoints solves the inverse distortion iteratively. Its default (5 iterations) leaves
# ~0.1 px error near the image corners at k1 = -0.24, so iterate to convergence instead.
UNDISTORT_CRITERIA = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-12)


def pixel_aspect(lens: LensModel | None) -> float:
    """fy / fx of the camera matrix (see model.PIXEL_ASPECT_DEFINITION); 1.0 without a lens model."""
    if lens is None:
        return 1.0
    K = np.asarray(lens.K, dtype=np.float64)
    return float(K[1, 1] / K[0, 0])


def radial_fold_limit_r2(lens: LensModel) -> float:
    """Largest normalised r^2 up to which the radial forward map r_d = r (1 + k1 r^2 + k2 r^4 + k3 r^6) is monotonic.

    d r_d / d r = 1 + 3 k1 u + 5 k2 u^2 + 7 k3 u^3 with u = r^2; the limit is its smallest positive root (inf if none).
    For k2 = k3 = 0 this is 1 / (3 |k1|) for k1 < 0 (the original k1-only rule) and inf for k1 >= 0.
    Tangential terms are not supported by this guard (calibration_w_hogline_v2 never estimates them).
    """
    d = np.zeros(5)
    raw = np.asarray(lens.dist, dtype=np.float64).ravel()
    d[:min(5, raw.size)] = raw[:5]
    if raw.size > 5 and np.any(raw[5:] != 0):
        raise NotImplementedError("fold-over guard: only k1, k2 (and k3) radial terms are supported")
    k1, k2, p1, p2, k3 = d
    if p1 != 0.0 or p2 != 0.0:
        raise NotImplementedError("fold-over guard: tangential distortion (p1, p2) is not supported")
    roots = np.roots(np.trim_zeros([7.0 * k3, 5.0 * k2, 3.0 * k1, 1.0], "f"))
    pos = [r.real for r in np.atleast_1d(roots) if abs(r.imag) < 1e-12 and r.real > 0]
    return float(min(pos)) if pos else float("inf")


def within_invertible_range(undistorted_px: np.ndarray, lens: LensModel) -> np.ndarray:
    """True where an undistorted pixel maps one-to-one onto the raw image under the radial model (k1, k2, k3).

    Beyond the fold-over radius the forward map folds back, so ice points far outside the camera's view would otherwise
    land on real-looking raw pixels. calibration_w_hogline_v2: k2 (and k3) are included; normalisation uses K, i.e. the
    (possibly shifted) principal point (cx, cy) and fy = pixel_aspect * fx.
    """
    pts = np.asarray(undistorted_px, dtype=np.float64).reshape(-1, 2)
    limit = radial_fold_limit_r2(lens)
    if not np.isfinite(limit):
        return np.ones(len(pts), dtype=bool)
    K = np.asarray(lens.K, dtype=np.float64)
    r2 = np.sum(((pts - K[:2, 2]) / np.diag(K)[:2]) ** 2, axis=1)
    return r2 < limit


def lens_parameters(lens: LensModel) -> dict:
    """Readable parameters of a radial lens (fx, fy, cx, cy, pixel aspect, k1, k2)."""
    K = np.asarray(lens.K, dtype=np.float64)
    d = np.zeros(5)
    raw = np.asarray(lens.dist, dtype=np.float64).ravel()
    d[:min(5, raw.size)] = raw[:5]
    return {"fx": float(K[0, 0]), "fy": float(K[1, 1]), "cx": float(K[0, 2]), "cy": float(K[1, 2]),
            "pixel_aspect": float(K[1, 1] / K[0, 0]), "k1": float(d[0]), "k2": float(d[1])}


def max_image_r2(lens: LensModel, image_size) -> float:
    """Largest normalised undistorted r^2 reached by the raw image (its corners and edge midpoints)."""
    w, h = image_size
    pts = np.array([[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1], [(w - 1) / 2, 0], [(w - 1) / 2, h - 1],
                    [0, (h - 1) / 2], [w - 1, (h - 1) / 2]], dtype=np.float64)
    K = np.asarray(lens.K, dtype=np.float64)
    und = undistort_pixels(pts, lens) if lens.has_distortion() else pts
    return float(np.max(np.sum(((und - K[:2, 2]) / np.diag(K)[:2]) ** 2, axis=1)))


def undistort_pixels(pts_px: np.ndarray, lens: LensModel) -> np.ndarray:
    """(N, 2) raw image pixels -> (N, 2) undistorted pixels (same camera matrix K)."""
    K = np.asarray(lens.K, dtype=np.float64)
    pts = np.asarray(pts_px, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.undistortPoints(pts, K, np.asarray(lens.dist, dtype=np.float64), None, None, K,
                               UNDISTORT_CRITERIA).reshape(-1, 2)


def distort_pixels(pts_px: np.ndarray, lens: LensModel) -> np.ndarray:
    """(N, 2) undistorted pixels -> (N, 2) raw image pixels, via cv2.projectPoints."""
    K = np.asarray(lens.K, dtype=np.float64)
    pts = np.asarray(pts_px, dtype=np.float64).reshape(-1, 2)
    rays = np.column_stack([pts, np.ones(len(pts))]) @ np.linalg.inv(K).T   # normalized (x, y, 1)
    out, _ = cv2.projectPoints(rays.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K,
                               np.asarray(lens.dist, dtype=np.float64))
    return out.reshape(-1, 2)
