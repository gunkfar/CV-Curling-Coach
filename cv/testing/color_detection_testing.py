from pathlib import Path
import sys
import cv2
from ultralytics import YOLO



MODEL_PATH = "../models/v1/best.pt"
# only green and yellow for now
COLOR_VALUES = {
    "green": (0, 128, 0),
    "yellow": (128, 128, 0)
}


def color_detection(rgb):
    """Return the named color closest to an RGB value."""
    # iterate over COLOR_VALUES and return the color with the minimum Euclidean distance to the input RGB value
    # need to ask Andy about how curling.gg API wants data to be inputted, but this is working for the time being
    return min(
        COLOR_VALUES,
        key=lambda name: sum(
            (value - ref) ** 2
            for value, ref in zip(rgb, COLOR_VALUES[name])
        ),
    )


def predict_and_display(image_path):
    """Predict objects and their color based on the center pixel of the bounding box, and display the annotated image."""
    model = YOLO(MODEL_PATH)
    result = model.predict(source=image_path)[0] # returns a list of results, we take the first one since we only have one image
    annotated_image = result.plot()

    for box in result.boxes.xyxy.tolist():
        # get the center pixel of the bounding box
        x1, y1, x2, y2 = map(int, box)
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        # get the RGB value of the center pixel
        blue, green, red = result.orig_img[center_y, center_x]
        rgb = (int(red), int(green), int(blue))

        # get closest color from COLOR_VALUES and box rock in that color
        color_name = color_detection(rgb)
        border_bgr = tuple(reversed(COLOR_VALUES[color_name]))
        cv2.rectangle(
            annotated_image,
            (x1, y1),
            (x2, y2),
            border_bgr,
            thickness=3,
        )
        print(f"Center pixel RGB {rgb}: {color_name}")

    cv2.imshow("Rock Detection with Colors", annotated_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Error: Usage is python color_detection_testing.py <image-path>")

    predict_and_display(sys.argv[1])
