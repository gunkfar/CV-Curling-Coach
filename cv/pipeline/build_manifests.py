"""
Builds a manifest for each game in progress at a given time: the game's
info plus the names of its images in the league bucket, grouped by camera.

The manifest is the hand-off to the detection side. It only lists image
names; images stay in the bucket and are loaded with frame_loader.load_image.

Usage (from the repo root):
    python cv/pipeline/build_manifests.py 2026-10-26T19:00

A time without an offset is treated as Denver time, matching the draw API.
Manifests are saved to cv/pipeline/manifests/ (testing output; don't commit).
"""

import json
import os
import sys
from datetime import datetime, timedelta

from frame_loader import DENVER, list_keys_in_window, make_s3_client
from games import get_games_at


# Cameras for each sheet
# The glass-end camera (7-12) is listed first, since games usually start there.
SHEET_TO_CAMERAS = {
    "A": ["camera7", "camera1"],
    "B": ["camera8", "camera2"],
    "C": ["camera9", "camera3"],
    "D": ["camera10", "camera4"],
    "E": ["camera11", "camera5"],
    "F": ["camera12", "camera6"],
}

# Extra time around the scheduled draw, since games start and end at
# slightly different times. Starting values; adjust as we learn more.
BUFFER_BEFORE = timedelta(minutes=10)
BUFFER_AFTER = timedelta(minutes=30)


def build_manifest(s3_client, game):
    """
    Return a manifest dictionary for one game (as returned by
    games.get_games_at), listing its images per camera.
    """
    cameras = SHEET_TO_CAMERAS.get(game["sheet"])
    if cameras is None:
        # Clear error if the API ever returns a sheet we don't know about
        raise ValueError(f"No cameras known for sheet '{game['sheet']}'")

    window_start = game["start"] - BUFFER_BEFORE
    window_end = game["end"] + BUFFER_AFTER

    images = {}
    for camera in cameras:
        images[camera] = list_keys_in_window(s3_client, camera, window_start, window_end)

    # Datetimes can't be saved to JSON directly, so store them as ISO text
    return {
        "league": game["league"],
        "sheet": game["sheet"],
        "team1": game["team1"],
        "team2": game["team2"],
        "scheduled_start": game["start"].isoformat(),
        "scheduled_end": game["end"].isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "images": images,
    }


def manifest_filename(manifest):
    """e.g. 2026-10-26_monday-open_sheetA.json"""
    date = manifest["scheduled_start"][:10]                 # '2026-10-26'
    league = manifest["league"].lower().replace(" ", "-")   # 'monday-open'
    return f"{date}_{league}_sheet{manifest['sheet']}.json"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cv/pipeline/build_manifests.py 2026-10-26T19:00")
        sys.exit(1)

    t = datetime.fromisoformat(sys.argv[1])
    if t.tzinfo is None:
        t = t.replace(tzinfo=DENVER)  # no offset given -> Denver time

    games = get_games_at(t)
    if not games:
        print("No games in progress at", t.isoformat())
        sys.exit(0)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "manifests")
    os.makedirs(out_dir, exist_ok=True)

    s3 = make_s3_client()  # one client, reused for every game

    for game in games:
        manifest = build_manifest(s3, game)
        path = os.path.join(out_dir, manifest_filename(manifest))

        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)

        counts = ", ".join(f"{cam}: {len(keys)}" for cam, keys in manifest["images"].items())
        print(f"Sheet {manifest['sheet']} ({counts}) -> {path}")