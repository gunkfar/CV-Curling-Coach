"""Named top-down views. A view is only a choice of ice region and resolution; any region can be used.

Ice frame: origin at the tee, +X toward the back line, +Y 90 degrees counter-clockwise, meters. In the output
image +X points right and +Y points up. The "wide" view extends toward -X (the hog line side) and matches the
settings used for the v2 development reports; it shows real pixels only where the camera sees ice.
"""

from dataclasses import dataclass, replace

import numpy as np

from .model import CameraCalibration
from .rectify import topdown_coverage, topdown_image


@dataclass(frozen=True)
class View:
    x_range_m: tuple[float, float]
    y_range_m: tuple[float, float]
    px_per_m: float


VIEWS = {
    "house": View((-2.5, 2.5), (-2.5, 2.5), 200.0),
    "wide": View((-7.0, 2.5), (-2.6, 2.6), 120.0),
}


def get_view(view="house", x_range_m=None, y_range_m=None, px_per_m=None) -> View:
    """A named view ("house", "wide") or a View, with optional overrides of any of its settings."""
    if isinstance(view, str):
        if view not in VIEWS:
            raise KeyError(f"Unknown view {view!r}; expected one of {list(VIEWS)}")
        view = VIEWS[view]
    view = replace(view,
                   x_range_m=tuple(x_range_m) if x_range_m is not None else view.x_range_m,
                   y_range_m=tuple(y_range_m) if y_range_m is not None else view.y_range_m,
                   px_per_m=float(px_per_m) if px_per_m is not None else view.px_per_m)
    if not (view.x_range_m[0] < view.x_range_m[1] and view.y_range_m[0] < view.y_range_m[1]):
        raise ValueError(f"View ranges need MIN < MAX, got x={view.x_range_m} y={view.y_range_m}")
    return view


def topdown(cal: CameraCalibration, img: np.ndarray, view="house", **overrides) -> tuple[np.ndarray, np.ndarray]:
    """Top-down image of a camera frame for a named view or View. Returns (image, ice_to_output_pixel 3x3).

    Overrides: x_range_m, y_range_m, px_per_m.
    """
    v = get_view(view, **overrides)
    return topdown_image(cal, img, v.x_range_m, v.y_range_m, v.px_per_m)


def coverage(cal: CameraCalibration, view="house", image_size=None, **overrides) -> np.ndarray:
    """(h, w) bool mask of top-down pixels backed by real camera pixels (False = black, not visible)."""
    v = get_view(view, **overrides)
    return topdown_coverage(cal, v.x_range_m, v.y_range_m, v.px_per_m, image_size)
