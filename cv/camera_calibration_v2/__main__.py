"""CLI: python -m cv.camera_calibration_v2 {list,topdown,pixel-to-ice,ice-to-pixel} ..."""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from .cameras import describe, list_calibrations, load_camera
from .transform import IcePlaneMapper
from .views import VIEWS, get_view, topdown


def _pairs(values) -> np.ndarray:
    if len(values) % 2:
        raise SystemExit("Give coordinates as X Y pairs")
    return np.array(values, dtype=float).reshape(-1, 2)


def _cmd_list(args) -> int:
    for name, path in list_calibrations().items():
        print(f"{name}  ({path.parent.name}/{path.name})")
    return 0


def _cmd_topdown(args) -> int:
    cal = load_camera(args.calibration)
    view = get_view(args.view, args.x_range, args.y_range, args.px_per_m)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = Path(args.calibration).name
    label = Path(args.calibration).name.removesuffix(".json")
    print(describe(cal))
    print(f"view {args.view}: X {view.x_range_m[0]:+.2f}..{view.x_range_m[1]:+.2f} m, "
          f"Y {view.y_range_m[0]:+.2f}..{view.y_range_m[1]:+.2f} m at {view.px_per_m:g} px/m")
    for image in args.images:
        img = cv2.imread(str(image))
        if img is None:
            print(f"Could not read {image}", file=sys.stderr)
            return 1
        out, _ = topdown(cal, img, view)
        # the calibration name is part of the file name so outputs of different candidates never overwrite each other
        path = out_dir / f"{Path(image).stem}_{label}_{args.view}.png"
        if not cv2.imwrite(str(path), out):
            print(f"Could not write {path}", file=sys.stderr)
            return 1
        print(f"  wrote {path}")
    return 0


def _cmd_pixel_to_ice(args) -> int:
    """Convert image pixel coordinates to ice-plane coordinates in meters."""
    cal = load_camera(args.calibration)
    print(describe(cal))
    pts = _pairs(args.xy)
    for (u, v), (x, y) in zip(pts, IcePlaneMapper(cal).image_to_ice(pts)):
        print(f"pixel ({u:.1f}, {v:.1f}) -> ice X={x:+.4f} m, Y={y:+.4f} m")
    return 0


def _cmd_ice_to_pixel(args) -> int:
    cal = load_camera(args.calibration)
    print(describe(cal))
    pts = _pairs(args.xy)
    for (x, y), (u, v) in zip(pts, IcePlaneMapper(cal).ice_to_image(pts)):
        print(f"ice X={x:+.4f} m, Y={y:+.4f} m -> pixel ({u:.1f}, {v:.1f})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cv.camera_calibration_v2", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list the bundled saved calibrations")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("topdown", help="top-down images of camera frames")
    p.add_argument("--calibration", required=True, help="calibration name (see list) or path to a .json")
    p.add_argument("--view", choices=list(VIEWS), default="house")
    p.add_argument("--x-range", nargs=2, type=float, metavar=("MIN", "MAX"), help="override the view's ice X range (m)")
    p.add_argument("--y-range", nargs=2, type=float, metavar=("MIN", "MAX"), help="override the view's ice Y range (m)")
    p.add_argument("--px-per-m", type=float, help="override the view's output resolution")
    p.add_argument("--out-dir", required=True)
    p.add_argument("images", nargs="+")
    p.set_defaults(func=_cmd_topdown)

    for name, func, what in (("pixel-to-ice", _cmd_pixel_to_ice, "image pixels (X Y ...) -> ice meters"),
                             ("ice-to-pixel", _cmd_ice_to_pixel, "ice meters (X Y ...) -> image pixels")):
        p = sub.add_parser(name, help=what)
        p.add_argument("--calibration", required=True)
        p.add_argument("xy", nargs="+", type=float, metavar="N")
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise SystemExit(f"error: {exc}") from None


if __name__ == "__main__":
    sys.exit(main())
