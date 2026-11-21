"""python -m cv.camera_calibration_v2.training_image_gui"""

import sys

try:
    from .window import main
except ImportError as e:
    if "PySide6" not in str(e):
        raise
    sys.exit("PySide6 is required for this tool. Install it with:\n"
             "    python -m pip install -r cv/camera_calibration_v2/training_image_gui/requirements.txt")

sys.exit(main())
