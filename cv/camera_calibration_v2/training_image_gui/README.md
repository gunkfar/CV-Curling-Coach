# Training Image Transformer

Desktop tool that turns original 1280 × 1024 camera frames into top-down PNGs for manual annotation / YOLO training data. It is a thin GUI around the existing
`cv.camera_calibration_v2` renderer (`cameras.load_camera` + `views.topdown`, the same code behind `render_topdown` / `render_batch`); no calibration or
rendering maths lives here. It is **not** part of the live game pipeline and the calibration runtime does not depend on it.

## Install and launch (Windows 11 / macOS)
From the repository root:
```
python -m pip install -r cv/camera_calibration_v2/training_image_gui/requirements.txt     # PySide6, opencv-python, numpy
python -m cv.camera_calibration_v2.training_image_gui
```
PySide6 is needed only for this tool; the calibration package itself still needs just `opencv-python` and `numpy`.

## Use
1. Choose the **Camera** (nothing is assumed from file names) and the **Output View** (`wide` by default, or `house`).
2. Add images: drag files onto the window, or **Add Images…**. Each file is fully decoded and must be JPG/JPEG/PNG and exactly 1280 × 1024; anything else is
   rejected with a reason and the rest are still added. Duplicates (same file, by path) are skipped. **Remove Selected** / **Clear All** edit the list.
3. Click an image in the list to preview its top-down view (not saved).
4. Pick the **Output folder** (you are offered to create it if it does not exist) and click **Transform Images**. Progress is shown; **Cancel** stops after the current image.

Outputs are lossless PNGs named `<source name>_camera<N>_<view>.png`, e.g. `camera6_20260519_154543_camera6_wide.png` (`wide` 1140 × 624, `house` 1000 × 1000).
Existing files are never overwritten (that image is reported as skipped); source images are never modified. A failing image is reported and the batch continues.

Notes: every bundled calibration is currently marked UNVERIFIED (shown as a non-blocking notice). If a file name says `cameraN_` and N is not the selected camera you are
asked to confirm. Top-down images are correct only for the ice surface.

## Files
`logic.py` (no Qt: validation, calibration choice, output naming, batch), `window.py` (PySide6 window and worker thread), `__main__.py` (entry point).
Tests: `cv/camera_calibration_v2/tests/test_training_gui_logic.py` (no PySide6 needed) and `test_training_gui_window.py` (runs offscreen, skipped without PySide6).
