"""
Pulls one image from the team's R2 (S3-compatible) bucket and
loads it into OpenCV, without saving anything to disk.

Setup (connection settings, constants, and client creation) is adapted from
cv/testing/s3Reader.py

Run from the repo root with virtual environment active:
    python cv/testing/learning/s3_to_opencv.py
"""

import os
import numpy as np
import cv2 # OpenCV
import boto3 # Library for talking to S3 buckets
from dotenv import load_dotenv # Read secrets from the .env file

# Load environment variables from .env
load_dotenv()
# Read each setting once and store it in a constant
# ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
# ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
# SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
# BUCKET_NAME = os.getenv("BUCKET_NAME")

ENDPOINT_URL = os.getenv("LEAGUE_R2_ENDPOINT_URL")
ACCESS_KEY = os.getenv("LEAGUE_R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("LEAGUE_R2_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("LEAGUE_BUCKET_NAME")

VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

# Initialize S3 client for Cloudflare R2
s3_client = boto3.client(
    service_name='s3',
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

# List some file names
# Ask the bucket for its first 20 files
response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=20)

# The answer is a dictionary
image_keys = []
for obj in response.get('Contents', []):
    key = obj['Key']
    print(key)
    if key.lower().endswith(VALID_EXTENSIONS):
        image_keys.append(key)

if not image_keys:
    raise RuntimeError("No images found in the first 20 files.")

# Download one image into memory
key = image_keys[0]
response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
image_bytes = response['Body'].read()

# The bridge: convert the bytes into an OpenCV image
# OpenCV only accepts NumPy arrays
arr = np.frombuffer(image_bytes, dtype=np.uint8)
# Decompress the JPEG into a grid of pixels shaped (height, width, 3)
# Colors are in BGR order
img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

if img is None:
    raise ValueError(f"OpenCV could not decode '{key}'")

print(f"Loaded '{key}' with shape {img.shape}")

# Shrink to half size so it fits on screen
preview = cv2.resize(img, None, fx=0.5, fy=0.5)
cv2.imshow(key, preview)
cv2.waitKey(0)
cv2.destroyAllWindows()
