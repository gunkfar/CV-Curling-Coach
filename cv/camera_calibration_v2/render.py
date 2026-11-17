"""Convenience interface: top-down images from in-memory camera frames using the 12 bundled v2 calibrations.

    from cv.camera_calibration_v2 import render_topdown, render_batch
    topdown = render_topdown(image, camera_id=6)                 # "wide" by default
    results = render_batch(images, camera_id=6, view="house")

Thin wrappers over the existing `load_camera` and `topdown` (views.py / rectify.py): no new calibration or warping code. Nothing is written to disk and the
input images are never modified.
"""

import numpy as np

from .cameras import load_camera
from .views import VIEWS, topdown

CAMERA_IDS = tuple(range(1, 13))


def _check_camera_id(camera_id):
    if isinstance(camera_id, bool) or not isinstance(camera_id, (int, np.integer)) or int(camera_id) not in CAMERA_IDS:
        raise ValueError(f"camera_id must be an integer from 1 to 12, got {camera_id!r}")
    return int(camera_id)


def _check_view(view):
    if not isinstance(view, str) or view not in VIEWS:
        raise ValueError(f"view must be one of {list(VIEWS)}, got {view!r}")
    return view


def _check_image(image, index=None):
    where = "image" if index is None else f"images[{index}]"

    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise ValueError(
            f"{where} must be a non-empty OpenCV-style NumPy array"
        )

    if image.shape[:2] != (1024, 1280):
        raise ValueError(
            f"{where} must be 1280x1024 pixels, "
            f"got {image.shape[1]}x{image.shape[0]}"
        )

    return image


def _render(cal, image, view):
    out, _ = topdown(cal, image, view)
    return out


def render_topdown(image, camera_id, view="wide"):
    """Top-down image of one frame from camera `camera_id` (1-12). view: "wide" (default) or "house". Returns a new NumPy array."""
    cam, view = _check_camera_id(camera_id), _check_view(view)
    return _render(load_camera(f"camera{cam}"), _check_image(image), view)


def render_batch(images, camera_id, view="wide"):
    """Top-down images of several frames from the same camera, in input order (empty input -> []). The calibration is loaded once."""
    cam, view = _check_camera_id(camera_id), _check_view(view)
    if isinstance(images, np.ndarray):
        images = list(images) if images.ndim == 4 else [images]
    images = list(images)
    for i, im in enumerate(images):
        _check_image(im, i)
    if not images:
        return []
    cal = load_camera(f"camera{cam}")
    return [_render(cal, im, view) for im in images]
