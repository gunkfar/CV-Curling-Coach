"""Top-down (ice-plane) image generation.

The output is metrically correct only for things lying on the ice. Anything
above it (stones, people, brooms) appears displaced and stretched.
"""

import cv2
import numpy as np

from .model import CameraCalibration
from .transform import IcePlaneMapper


def ice_to_topdown_matrix(x_range_m, y_range_m, px_per_m: float) -> tuple[np.ndarray, tuple[int, int]]:
    """Matrix mapping ice (X, Y, 1) to top-down output pixels, and the output size (w, h).

    Output layout: +X points right and +Y points up, so the image reads as the
    ice seen from above.
    """
    x0, x1 = x_range_m
    y0, y1 = y_range_m
    A = np.array([[px_per_m, 0.0, -x0 * px_per_m],
                  [0.0, -px_per_m, y1 * px_per_m],
                  [0.0, 0.0, 1.0]])
    size = (int(round((x1 - x0) * px_per_m)), int(round((y1 - y0) * px_per_m)))
    return A, size


def _output_grid_ice(A: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """(h, w, 2) ice coordinates (m) of every top-down output pixel (pixel centers at integer coords)."""
    w, h = size
    grid = np.stack(np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64)), -1)
    return cv2.perspectiveTransform(grid.reshape(-1, 1, 2), np.linalg.inv(A)).reshape(h, w, 2)


def topdown_coverage(cal: CameraCalibration, x_range_m=(-2.5, 2.5), y_range_m=(-2.5, 2.5),
                     px_per_m: float = 200.0, image_size=None) -> np.ndarray:
    """(h, w) bool mask of top-down pixels that are sampled from real camera pixels.

    False means outside the camera's field of view (or outside the lens model's invertible range); those
    pixels are black in topdown_image and carry no information. `image_size` is (width, height).
    """
    A, size = ice_to_topdown_matrix(x_range_m, y_range_m, px_per_m)
    ice = _output_grid_ice(A, size)
    return IcePlaneMapper(cal).ice_in_view(ice.reshape(-1, 2), image_size).reshape(ice.shape[:2])


def topdown_image(cal: CameraCalibration, img: np.ndarray, x_range_m=(-2.5, 2.5),
                  y_range_m=(-2.5, 2.5), px_per_m: float = 200.0) -> tuple[np.ndarray, np.ndarray]:
    """Warp a camera image onto the ice plane.

    The output covers `x_range_m` x `y_range_m` (ice meters, +X right, +Y up) at `px_per_m` pixels per meter.
    Output pixel centers sit at ice (x0 + u / px_per_m, y1 - v / px_per_m), so views whose bounds differ by a
    whole number of output pixels share exactly the same pixel grid. Areas the camera does not see are black;
    see topdown_coverage for the mask.

    Returns the top-down image and the 3x3 matrix mapping ice coords (m) to its pixels.
    """
    A, size = ice_to_topdown_matrix(x_range_m, y_range_m, px_per_m)
    if cal.lens is None or not cal.lens.has_distortion():
        image_to_topdown = A @ np.linalg.inv(cal.H_ice_to_image)
        out = cv2.warpPerspective(img, image_to_topdown, size, flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return out, A
    # With distortion the image -> ice map is not a homography: look up, for every output pixel,
    # where its ice point lands in the raw image, then sample with cv2.remap.
    w, h = size
    ice = _output_grid_ice(A, size).reshape(-1, 2)
    mapper = IcePlaneMapper(cal)
    src = mapper.ice_to_image(ice).reshape(h, w, 2)
    # The distortion model folds back far from the image; never sample there (it would show ghost pixels).
    # margin_px=1: only remove fold-over / behind-camera points; cv2.remap handles the image border itself.
    src[~mapper.ice_in_view(ice, (img.shape[1], img.shape[0]), margin_px=1.0).reshape(h, w)] = -1.0
    src = src.astype(np.float32)
    out = cv2.remap(img, src[..., 0], src[..., 1], cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out, A


def undistorted_image(cal: CameraCalibration, img: np.ndarray) -> np.ndarray:
    """The camera image with lens distortion removed (cv2.undistort, same camera matrix K).

    Its pixels are the coordinates H_ice_to_image maps to, so straight painted lines should be straight.
    Returns a copy of the input when the calibration has no distortion model.
    """
    if cal.lens is None or not cal.lens.has_distortion():
        return img.copy()
    K = np.asarray(cal.lens.K, dtype=np.float64)
    return cv2.undistort(img, K, np.asarray(cal.lens.dist, dtype=np.float64), None, K)
