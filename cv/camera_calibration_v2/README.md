# camera_calibration_v2

Self-contained runtime for the accepted **v2 HOG 1.422** calibrations of all 12 cameras. It loads a saved calibration, converts original-image pixels to ice
coordinates in metres (and back), and produces top-down (rectified) images. It only **applies** calibrations: no fitting, annotation or validation code.

## Status
Model of every profile (schema 2, `radial_k1_k2_cy`): ice (X, Y) --homography H--> undistorted pixels --radial lens (k1, k2, vertical centre cy, cx at the image centre,
fx = 1280, fy = 1.422 fx)--> raw pixels. `provenance.verified` is `false` in all twelve; errors were measured against painted geometry, **not** stone-position accuracy.
Ice frame: origin at the tee, +X toward the back line, +Y 90 degrees counter-clockwise seen from above, metres. Top-down images show +X right, +Y up.

"House left" means the back line is at the image left: +X points to image left and +Y to image down (cameras 1-6); "house right": +X right, +Y up (cameras 7-12). Orientation was assumed
(unmirrored image), not surveyed.

## Input
Input images must be 1280 × 1024 pixels, matching the resolution used during calibration. Resized or cropped images cannot be passed directly to the rendering functions.

## Use (run from the repository root)
```python
import cv2, numpy as np
import cv.camera_calibration_v2 as cc

cal = cc.load_camera("camera3")                      # "camera1" ... "camera12", or a path to a .json
print(cc.describe(cal))
mapper = cc.IcePlaneMapper(cal)

# original-image pixels (u, v) -> ice metres (X, Y)
ice = mapper.image_to_ice(np.array([[640.0, 512.0], [300.0, 500.0]]))
# ice metres -> original-image pixels
px = mapper.ice_to_image(np.array([[0.0, 0.0], [-6.401, 0.0]]))      # tee, house-side hog-line edge
inside = mapper.ice_in_view(np.array([[-6.4, 0.0], [-30.0, 0.0]]))   # False where the lens model / camera does not see that ice point

# top-down image of any frame from the same camera: view "house" (X,Y +-2.5 m, 200 px/m) or "wide" (X -7..2.5, Y +-2.6 m, 120 px/m)
img = cv2.imread("frame.jpg")
out, ice_to_output_pixel = cc.topdown(cal, img, "wide")             # overrides: x_range_m=, y_range_m=, px_per_m=
mask = cc.coverage(cal, "wide")                                     # True where the output has real camera pixels
```
Command line:
```
python -m cv.camera_calibration_v2 list
python -m cv.camera_calibration_v2 pixel-to-ice --calibration camera1 640 512 300 500
python -m cv.camera_calibration_v2 ice-to-pixel --calibration camera9 0 0 -6.401 0
python -m cv.camera_calibration_v2 topdown --calibration camera12 --view wide --out-dir out frame1.jpg frame2.jpg
```
Other exported names: `load_calibration`, `save_calibration`, `CalibrationStore`, `camera_id_from_key`, `CameraCalibration`, `LensModel`, `IcePose`, `ParamStatus`, `SheetSpec`,
`topdown_image`, `topdown_coverage`, `undistorted_image`, `get_view`, `VIEWS`, `View`.

## Quick top-down rendering (in-memory)
```python
import cv2
from cv.camera_calibration_v2 import render_topdown, render_batch

topdown = render_topdown(cv2.imread("camera6_image.jpg"), camera_id=6)             # view="wide" is the default (X -7..2.5 m, Y +-2.6 m, 120 px/m)
house = render_topdown(image, camera_id=6, view="house")                          # X, Y +-2.5 m at 200 px/m
results = render_batch([img1, img2, img3], camera_id=6, view="wide")              # same camera for all; list in input order; [] -> []
cv2.imwrite("topdown.png", topdown)                                                # saving is up to you
```
Both functions take arrays already in memory (e.g. decoded from R2), return NEW arrays, never write files and never modify the input. `camera_id` is 1-12; `view` is `"wide"` or `"house"`
(other values raise `ValueError`). They wrap `load_camera` + `topdown`; the wide view keeps its established field of view (it is not the whole sheet).

## Dependencies and limitations
* Python 3.10+, `numpy`, `opencv-python` (`requirements.txt`). Nothing outside this folder is needed (checked by a test that blocks the `cv.calibration_versions` and `camera_calibration` imports).
* Pixel aspect fy/fx = 1.422 is an **assumption** (`status.pixel_aspect: assumed`); the lens is k1 + k2 + cy only (no k3, tangential terms or horizontal centre).
* Mapping is exact only for points ON the ice plane: stones and people are displaced by parallax (no camera pose / height is stored; `height_m != 0` raises). Far-field accuracy beyond the house is
  less certain (a known 12-ft ring hog-minus-back asymmetry of up to about 10-15 mm exists in several profiles; camera3 is soft-focused and the weakest, camera2's hog-line constraint rests on few points).
* The older `camera_calibration/` (now `cv/calibration_versions/camera_calibration/`) operations are all present (load, pixel-to-ice, ice-to-pixel, top-down, coverage, undistorted image); its k1-only calibrations are not included.

## Tests

Run from the repository root:

python -m unittest discover -s cv/camera_calibration_v2/tests -t .

Tests cover calibration loading, checksum verification, coordinate
transformations, rendering, and package independence.
