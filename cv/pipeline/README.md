# CV Image Pipeline

Selects the images for a curling game from the league bucket and loads them into OpenCV.

Given a time, the pipeline asks Rock Creek's draw API which games were in progress, finds each game's two cameras, and lists every image from those cameras during the game. The result is a **manifest**: the game's info plus the names of its images, grouped by camera.

The pipeline only selects images. It never copies, changes, or deletes them.

## Files

| File | What it does |
|---|---|
| `frame_loader.py` | Bucket access: list images by camera and time window, load an image into OpenCV |
| `games.py` | Looks up games in progress at a given time using the draw API |
| `build_manifests.py` | Builds and saves a manifest for each game at a given time |

## Setup

**1. Environment variables.** Copy the `LEAGUE_` lines from `.env.example` (repo root) into your `.env` and fill in the values from Andy.

**2. Packages.**

```
pip install boto3 python-dotenv numpy opencv-python requests tzdata
```

`tzdata` is required on Windows, which has no built-in time zone data.

## Usage

Run from the repo root.

**Build manifests** by running the script at the two standard query times for a date, 6:00 PM and 8:15 PM. These match the website's `gamesOnDate`, so CV and the UI see the same games.

```
python cv/pipeline/build_manifests.py 2026-10-26T18:00
python cv/pipeline/build_manifests.py 2026-10-26T20:15
```

A time without an offset is treated as Denver time. Manifests are saved to `cv/pipeline/manifests/` (test output; don't commit).

## What a manifest looks like

```json
{
  "league": "Monday Open",
  "sheet": "A",
  "team1": "Unicones",
  "team2": "Wideawake",
  "scheduled_start": "2026-10-26T18:30:00-06:00",
  "scheduled_end": "2026-10-26T20:45:00-06:00",
  "window_start": "2026-10-26T18:20:00-06:00",
  "window_end": "2026-10-26T21:15:00-06:00",
  "images": {
    "camera7": ["camera7_20261026_182741.jpg", "..."],
    "camera1": ["camera1_20261026_182803.jpg", "..."]
  }
}
```

The glass-end camera (7-12) is listed first, since games usually start at that end.

## Loading images in detection code
Load a manifest and call `load_image` for each image.

```python
import json
import sys

# Lets scripts outside cv/pipeline find frame_loader (run from the repo root)
sys.path.append("cv/pipeline")

from frame_loader import make_s3_client, load_image

with open("cv/pipeline/manifests/2026-10-26_monday-open_sheetA.json") as f:
    manifest = json.load(f)

s3 = make_s3_client()  # create once, reuse for every image

for camera, keys in manifest["images"].items():
    for key in keys:
        img = load_image(s3, key)  # NumPy array, (height, width, 3), BGR
        # ... run detection on img ...
```

## What we know about the data

- Image names look like `cameraN_YYYYMMDD_HHMMSS.jpg`, with timestamps in **Denver local time** (verified against the Oct 26 Monday Open draw schedule).
- Each sheet has two cameras, one per end (confirmed by Andy):

  | Sheet | A | B | C | D | E | F |
  |---|---|---|---|---|---|---|
  | Cameras | 7, 1 | 8, 2 | 9, 3 | 10, 4 | 11, 5 | 12, 6 |

- Recording mostly stops near the scheduled end; the 30-minute buffer after a game adds few images.

## Not handled yet

- **Finding every game on a date.** The draw API answers "what's in progress at this moment," so the pipeline takes a time, not a date.
- **Team colors.** There's no data on which team threw which colors.
- **Image transforms** (cropping, distortion correction). If these are added and results are stored, revisit storage with Andy.

## Notes

- The league bucket credentials are **read/write**. This pipeline only reads; don't add calls that write or delete without checking with the team.
- Buffer around each game: 10 minutes before, 30 after (`BUFFER_BEFORE` / `BUFFER_AFTER` in `build_manifests.py`). Starting values; adjust as we learn more.
