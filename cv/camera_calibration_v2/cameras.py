"""Finding and loading the saved calibrations that ship in `calibrations/`.

A calibration is identified by its file name without `.json`: "camera1" ... "camera12" (one accepted v2 HOG 1.422 profile per camera).
"""

from pathlib import Path

from .io import load_calibration
from .lens import pixel_aspect
from .model import CameraCalibration

CALIBRATIONS_DIR = Path(__file__).resolve().parent / "calibrations"


def list_calibrations(root=None) -> dict[str, Path]:
    """{name: path} of every '<name>.json' under `root` (default: the bundled calibrations/ folder)."""
    root = Path(root) if root is not None else CALIBRATIONS_DIR
    return {p.stem: p for p in sorted(root.rglob("*.json"))}


def load_camera(name_or_path, root=None) -> CameraCalibration:
    """Load a saved calibration by name (see list_calibrations), by camera id if unambiguous, or by file path."""
    path = Path(str(name_or_path))
    if path.suffix == ".json" or path.is_file():
        return load_calibration(path)
    available = list_calibrations(root)
    name = str(name_or_path)
    if name in available:
        return load_calibration(available[name])
    matches = [n for n in available if n.startswith(name + "_")]
    if len(matches) == 1:
        return load_calibration(available[matches[0]])
    if matches:
        raise ValueError(f"{name!r} has several saved calibrations; name one explicitly: {', '.join(matches)}")
    raise FileNotFoundError(f"No saved calibration {name!r}. Available: {', '.join(available) or '(none)'}")


def describe(cal: CameraCalibration) -> str:
    """One line saying which model this is and whether it is verified."""
    verified = "verified" if cal.provenance.get("verified") else "UNVERIFIED"
    if cal.lens is None or not cal.lens.has_distortion():
        return f"{cal.camera_id} ({verified}): homography only, no lens distortion"
    d = cal.lens.dist.ravel()
    basis = cal.status.get("pixel_aspect")
    basis = getattr(basis, "value", basis) or "n/a"
    return (f"{cal.camera_id} ({verified}): radial k1={float(d[0]):+.4f} k2={float(d[1]):+.4f} cy={float(cal.lens.K[1][2]):.1f}, "
            f"pixel aspect fy/fx={pixel_aspect(cal.lens):.3f} ({basis})")
