"""
Selects and loads curling images from the league R2 bucket.
 
1. parse_key           - read the camera and timestamp out of an image's name
2. list_keys_in_window - find every image from one camera within a time window
3. load_image          - download one image and decode it into OpenCV
 
Requirements:
    pip install boto3 python-dotenv numpy opencv-python tzdata
    (tzdata is needed on Windows, which has no built-in time zone data)
 
Environment variables (read from the .env file in the repo root; see .env.example):
    LEAGUE_R2_ENDPOINT_URL       - S3 API endpoint for the league bucket
    LEAGUE_R2_ACCESS_KEY_ID      - access key ID
    LEAGUE_R2_SECRET_ACCESS_KEY  - secret access key
    LEAGUE_BUCKET_NAME           - bucket name
 
Adapted connection setup from cv/testing/s3Reader.py.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
from dotenv import load_dotenv

import numpy as np
import cv2

# Load the new league bucket's settings from .env (same pattern as s3Reader.py)
load_dotenv()

ENDPOINT_URL = os.getenv("LEAGUE_R2_ENDPOINT_URL")
ACCESS_KEY = os.getenv("LEAGUE_R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("LEAGUE_R2_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("LEAGUE_BUCKET_NAME")

# Image filenames are in Denver local time
DENVER = ZoneInfo("America/Denver")

# Connection
def make_s3_client():
    # Create a client for the league bucket. This pipeline only reads from it.
    return boto3.client(
        service_name='s3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )

# Reading image names
def parse_key(key):
    # Turn an image name like 'camera4_20260315_143012.jpg' into ('camera4', datetime(2026, 3, 15, 14, 30, 12))

    # drop any folders in front
    filename = os.path.basename(key)
    # 'camera4_20260315_143012', '.jpg'
    name, _extension = os.path.splitext(filename)

    # ['camera4', '20260315', '143012']
    parts = name.split("_")
    if len(parts) != 3:
        return None

    camera, date_part, time_part = parts

    try:
        # %Y year, %m month, %d day, %H hour (24h), %M minutes, %S seconds
        timestamp = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
    except ValueError:
        return None

    return camera, timestamp

# Selecting images by camera and time
def list_keys_in_window(s3_client, camera, start, end):
    # Return the names of all images from one camera taken between start (included) and end (not included), in time order.
    # start and end must include a time zone, like the times from the API.
    
    keys = []
    # S3 returns at most 1,000 names per request. A paginator keeps asking
    # for the next batch until there are none left.
    paginator = s3_client.get_paginator("list_objects_v2")

    # Ask for one camera-day at a time. A window that crosses midnight
    # (a late game) covers two days, so loop over every day it touches.
    day = start.date()
    while day <= end.date():
        # The trailing underscore matters. S3 matches names by text, so
        # "camera1" would also match every "camera10", "camera11", and
        # "camera12" file. "camera1_" matches only camera 1.
        prefix = f"{camera}_{day:%Y%m%d}_"

        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
            # 'Contents' is missing when nothing matches, so default to []
            for obj in page.get("Contents", []):
                parsed = parse_key(obj["Key"])
                if parsed is None:
                    continue  # not a camera image; skip it

                _camera, taken_at = parsed
                taken_at = taken_at.replace(tzinfo=DENVER) # filenames are Denver time

                if start <= taken_at < end:
                    keys.append(obj["Key"])

        day += timedelta(days=1)

    # S3 lists names alphabetically, which within one camera is time order,
    # so keys is already sorted.
    return keys

# Loading an image into OpenCV
def load_image(s3_client, key):
    # Download one image from the league bucket and return it as an OpenCV image:
    # a NumPy array shaped (height, width, 3), colors in BGR order.
 
    # The image is kept in memory only; nothing is written to disk.
    download = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
    image_bytes = download['Body'].read() # still compressed JPEG data

    # Wrap the bytes in a NumPy array (OpenCV only accepts arrays), then
    # decompress them into pixels.
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError(f"OpenCV could not decode '{key}'")

    return img

# Quick manual test
if __name__ == "__main__":
    s3 = make_s3_client()

    # Monday Open, Oct 26: 6:30-8:45 PM
    start = datetime(2026, 10, 26, 18, 30, tzinfo=DENVER)
    end = datetime(2026, 10, 26, 20, 45, tzinfo=DENVER)

    keys = list_keys_in_window(s3, "camera12", start, end)
    print("Found", len(keys), "images")
    print("First:", keys[:3])
    print("Last: ", keys[-3:])

    img = load_image(s3, keys[0])
    print("Loaded", keys[0], "with shape", img.shape)

