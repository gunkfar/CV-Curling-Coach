"""JSON persistence for calibrations and annotations."""

import json
import re
from pathlib import Path

import numpy as np

from .model import (DISTORTION_MODELS, DISTORTION_RADIAL_K1, DISTORTION_RADIAL_K1_K2_CY, LEGACY_SCHEMA_VERSION, SCHEMA_VERSION,
                    SUPPORTED_SCHEMA_VERSIONS, CameraCalibration, IcePose, LensModel, ParamStatus)
from .sheet import SheetSpec

_CAMERA_KEY = re.compile(r"^(camera\d+)_")


def camera_id_from_key(key: str) -> str:
    """'camera6_20260519_154543.jpg' (or a path/bucket key ending in it) -> 'camera6'."""
    match = _CAMERA_KEY.match(Path(key).name)
    if not match:
        raise ValueError(f"Cannot parse camera id from {key!r}")
    return match.group(1)


def _array_or_none(value):
    return None if value is None else np.asarray(value, dtype=float)


def _is_legacy_lens(lens, image_size) -> bool:
    """True when the lens is exactly the original model: k1 only, principal point at the image centre."""
    if lens is None:
        return True
    d = np.asarray(lens.dist, dtype=float).ravel()
    K = np.asarray(lens.K, dtype=float)
    w, h = image_size
    return (lens.distortion_model == DISTORTION_RADIAL_K1 and not np.any(d[1:] != 0)
            and abs(K[0, 2] - (w - 1) / 2.0) < 1e-9 and abs(K[1, 2] - (h - 1) / 2.0) < 1e-9)


def required_schema_version(cal: CameraCalibration) -> int:
    """1 for the legacy lens model (readable by every package), 2 for anything else (rejected by the original packages)."""
    return LEGACY_SCHEMA_VERSION if _is_legacy_lens(cal.lens, cal.image_size) else SCHEMA_VERSION


def _lens_to_dict(lens, version):
    if lens is None:
        return None
    d = {"K": np.asarray(lens.K).tolist(), "dist": np.asarray(lens.dist).tolist(), "model": lens.model}
    if version >= 2:
        from .lens import lens_parameters
        # the tag follows the actual K / dist (authoritative): anything beyond the legacy model is radial_k1_k2_cy
        d["distortion_model"] = DISTORTION_RADIAL_K1_K2_CY
        d["parameters"] = lens_parameters(lens)
        d["convention"] = ("OpenCV pinhole: K = [[fx,0,cx],[0,fy,cy],[0,0,1]], fy = pixel_aspect*fx, dist = [k1,k2,p1,p2,k3] "
                           "with p1 = p2 = k3 = 0; x = (u-cx)/fx, y = (v-cy)/fy, x_d = x (1 + k1 r^2 + k2 r^4); K and dist are "
                           "authoritative, 'parameters' repeats them for reading and is checked on load")
    return d


def calibration_to_dict(cal: CameraCalibration) -> dict:
    version = required_schema_version(cal)
    return {
        "schema_version": version,
        "camera_id": cal.camera_id,
        "image_size": list(cal.image_size),
        "H_ice_to_image": np.asarray(cal.H_ice_to_image).tolist(),
        "lens": _lens_to_dict(cal.lens, version),
        "pose": None if cal.pose is None else {
            "rvec": np.asarray(cal.pose.rvec).ravel().tolist(),
            "tvec": np.asarray(cal.pose.tvec).ravel().tolist(),
        },
        "status": {k: ParamStatus(v).value for k, v in cal.status.items()},
        "sheet": cal.sheet.to_dict(),
        "valid_region_m": None if cal.valid_region_m is None else np.asarray(cal.valid_region_m).tolist(),
        "metrics": cal.metrics,
        "provenance": cal.provenance,
        "valid_from": cal.valid_from,
    }


def _lens_from_dict(lens: dict, version: int) -> LensModel:
    K = np.asarray(lens["K"], dtype=float)
    dist = np.asarray(lens["dist"], dtype=float)
    if dist.size > 5 or np.any(dist[2:] != 0):
        raise ValueError("Only radial k1/k2 distortion is supported (p1, p2, k3 must be 0)")
    if version == LEGACY_SCHEMA_VERSION:
        if dist.size > 1 and np.any(dist[1:] != 0):
            raise ValueError("Schema-1 calibration with distortion beyond k1: not a legacy file")
        return LensModel(K=K, dist=dist, model=lens.get("model", "pinhole"), distortion_model=DISTORTION_RADIAL_K1)
    model = lens.get("distortion_model")
    if model not in DISTORTION_MODELS:
        raise ValueError(f"Unknown lens distortion_model {model!r}; expected one of {DISTORTION_MODELS}")
    out = LensModel(K=K, dist=dist, model=lens.get("model", "pinhole"), distortion_model=model)
    params = lens.get("parameters")
    if params is not None:
        from .lens import lens_parameters
        actual = lens_parameters(out)
        for k, v in params.items():
            if k in actual and abs(actual[k] - float(v)) > 1e-9 * max(1.0, abs(float(v))):
                raise ValueError(f"Lens parameter {k}={v} disagrees with K/dist ({actual[k]})")
    if model == DISTORTION_RADIAL_K1 and dist.size > 1 and np.any(dist[1:] != 0):
        raise ValueError("distortion_model radial_k1 with a non-zero k2")
    return out


def calibration_from_dict(d: dict) -> CameraCalibration:
    version = d.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported calibration schema version {version!r}")
    lens = d.get("lens")
    pose = d.get("pose")
    return CameraCalibration(
        camera_id=d["camera_id"],
        image_size=tuple(d["image_size"]),
        H_ice_to_image=np.asarray(d["H_ice_to_image"], dtype=float),
        status={k: ParamStatus(v) for k, v in d["status"].items()},
        sheet=SheetSpec.from_dict(d["sheet"]),
        lens=None if lens is None else _lens_from_dict(lens, version),
        pose=None if pose is None else IcePose(
            rvec=np.asarray(pose["rvec"], dtype=float), tvec=np.asarray(pose["tvec"], dtype=float)),
        valid_region_m=_array_or_none(d.get("valid_region_m")),
        metrics=d.get("metrics", {}),
        provenance=d.get("provenance", {}),
        valid_from=d.get("valid_from", ""),
        schema_version=version,
    )


def save_calibration(cal: CameraCalibration, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(calibration_to_dict(cal), indent=2), encoding="utf-8")
    return path


def load_calibration(path) -> CameraCalibration:
    return calibration_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def load_annotation(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_annotation(annotation: dict, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(annotation, indent=2), encoding="utf-8")
    return path


class CalibrationStore:
    """A directory of '<camera_id>.json' calibration files."""

    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, camera_id: str) -> Path:
        return self.root / f"{camera_id}.json"

    def get(self, camera_id: str) -> CameraCalibration:
        path = self.path_for(camera_id)
        if not path.exists():
            raise FileNotFoundError(f"No calibration for {camera_id!r} in {self.root}")
        return load_calibration(path)

    def save(self, cal: CameraCalibration) -> Path:
        return save_calibration(cal, self.path_for(cal.camera_id))

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))
