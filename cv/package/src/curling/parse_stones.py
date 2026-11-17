import json
import math
from pathlib import Path

SHEET_CAMERA_MAP = {
    1: (1, 7),
    2: (2, 8),
    3: (3, 9),
    4: (4, 10),
    5: (5, 11),
    6: (6, 12),
}

def post_parse_lookback_and_fix(parsed_frames, double_gap_threshold=100.0):
    if not parsed_frames:
        return parsed_frames

    fixed_frames = []
    ends_dict = {}
    for pf in parsed_frames:
        end_num = pf.get("end_num", 0)
        if end_num not in ends_dict:
            ends_dict[end_num] = []
        ends_dict[end_num].append(pf)

    sorted_end_nums = sorted(ends_dict.keys())
    expected_ends = list(range(min(sorted_end_nums), min(sorted_end_nums) + len(sorted_end_nums))) if sorted_end_nums else []
    if sorted_end_nums != expected_ends:
        print(f"[GAME STATE WARNING] End sequence has gaps or is non-contiguous: detected ends are {sorted_end_nums}.")

    for end_num, frames_in_end in ends_dict.items():
        frames_in_end.sort(key=lambda x: x["time"])
        
        if len(frames_in_end) >= 17:
            fixed_frames.extend(frames_in_end)        
            if len(frames_in_end) != 17:
                print(f"[GAME STATE WARNING] End {end_num} has {len(frames_in_end)} frames. Each curling end should have exactly 17 frames.")
            continue

        rebuilt_end_frames = []
        
        for i in range(len(frames_in_end)):
            current_frame = frames_in_end[i]
            
            if i > 0:
                prev_frame = rebuilt_end_frames[-1]
                time_delta = current_frame["time"] - prev_frame["time"]
                
                # --- HELPER: Get added color between frames ---
                def get_added_color(frame_a, frame_b):
                    count_a = {"green": sum(1 for s in frame_a["stones"] if s["color"] == "green"),
                               "yellow": sum(1 for s in frame_a["stones"] if s["color"] == "yellow")}
                    count_b = {"green": sum(1 for s in frame_b["stones"] if s["color"] == "green"),
                               "yellow": sum(1 for s in frame_b["stones"] if s["color"] == "yellow")}
                    if count_b["green"] > count_a["green"]:
                        return "green"
                    elif count_b["yellow"] > count_a["yellow"]:
                        return "yellow"
                    return None

                color_violation = False
                if len(rebuilt_end_frames) >= 2:
                    col_prev_prev = get_added_color(rebuilt_end_frames[-2], rebuilt_end_frames[-1])
                    col_prev_curr = get_added_color(rebuilt_end_frames[-1], current_frame)
                    if col_prev_prev is not None and col_prev_curr is not None and col_prev_prev == col_prev_curr:
                        color_violation = True

                # --- HIERARCHICAL LOGIC WITH 16-FRAME GUARD ---
                # Double-hog only allowed if len(frames_in_end) <= 15 (meaning at least 2 frames are missing overall)
                if time_delta >= double_gap_threshold and len(frames_in_end) <= 15:
                    print(f"[LOOKBACK WARNING] End {end_num}: Large time gap of {time_delta:.1f}s detected "
                          f"between timestamp {prev_frame['time']:.1f}s and {current_frame['time']:.1f}s.")
                    print(f"[LOOKBACK FIX] Injecting 2 synthetic missing frames (Double Hogged Stones).")
                    
                    t1 = prev_frame["time"] + (time_delta / 3.0)
                    t2 = prev_frame["time"] + (2.0 * time_delta / 3.0)
                    for t_synth in [t1, t2]:
                        synth_frame = prev_frame.copy()
                        synth_frame["time"] = t_synth
                        synth_frame["shot_num"] = len(rebuilt_end_frames) + 1
                        synth_frame["source_filename"] = f"{prev_frame.get('source_filename', 'frame')}_synth_{len(rebuilt_end_frames) + 1}"
                        rebuilt_end_frames.append(synth_frame)
                
                elif color_violation:
                    # Primary Single-Hog Check (Color alternation break)
                    print(f"[LOOKBACK WARNING] End {end_num}: Single hog detected via Color Alternation Break "
                          f"between timestamp {prev_frame['time']:.1f}s and {current_frame['time']:.1f}s.")
                    print(f"[LOOKBACK FIX] Injecting 1 synthetic missing frame.")
                    
                    t_synth = prev_frame["time"] + (time_delta / 2.0)
                    synth_frame = prev_frame.copy()
                    synth_frame["time"] = t_synth
                    synth_frame["shot_num"] = len(rebuilt_end_frames) + 1
                    synth_frame["source_filename"] = f"{prev_frame.get('source_filename', 'frame')}_synth_{len(rebuilt_end_frames) + 1}"
                    rebuilt_end_frames.append(synth_frame)

            current_frame["shot_num"] = len(rebuilt_end_frames) + 1
            rebuilt_end_frames.append(current_frame)

        # --- TRAILING PASS: Catch last-stone(s) hogged where no subsequent frame exists ---
        while len(rebuilt_end_frames) < 17:
            last_frame = rebuilt_end_frames[-1]
            synth_time = last_frame["time"] + 40.0
            synth_frame = last_frame.copy()
            synth_frame["time"] = synth_time
            synth_frame["shot_num"] = len(rebuilt_end_frames) + 1
            synth_frame["source_filename"] = f"{last_frame.get('source_filename', 'frame')}_synth_trailing_{len(rebuilt_end_frames) + 1}"
            print(f"[LOOKBACK FIX] End {end_num}: Injecting trailing synthetic frame at {synth_time:.1f}s (Last Stone Hogged case).")
            rebuilt_end_frames.append(synth_frame)

        if len(rebuilt_end_frames) != 17:
            print(f"[GAME STATE WARNING] End {end_num} resulted in {len(rebuilt_end_frames)} frames after lookback. Each curling end should have exactly 17 frames.")

        fixed_frames.extend(rebuilt_end_frames)
        
    return fixed_frames

def parse_curling_frames(input_dir="raw_data", output_dir="parsed_data", sheet_num = 1, yolo_tolerance=2.5):
    # Setup input and output directories for JSON
    json_in = Path(input_dir) / "json" #input folder must contain just the frames of the two cameras for that specific sheet for that game, any json combining must come post parsing
    json_out = Path(output_dir) / "json"
    json_out.mkdir(parents=True, exist_ok=True) 


    print(f"Parsing frames and detecting ends from '{input_dir}'...")

    # Load all sorted frame JSON files from the input directory
    json_files = list(json_in.glob("*.json"))
    frames = []
    for jf in json_files:
        with open(jf, "r") as f:
            data = json.load(f)
            data["source_filename"] = jf.stem  # Store the original filename stem
            frames.append(data)

    # Guard clause if no frames are found
    if not frames:
        print("No frames found to parse.")
        return

    frames.sort(key=lambda x: x["time"])

    parsed_frames = []
    current_end = 0 #can use this var to add end num to jsons
    current_shot_number = 0 #DONT use this var to add shot num to jsons, backwards edge case code later gives (hopefully) correct final num shot
    max_stones_in_current_end = 0

    cam_house_1, cam_house_2 = SHEET_CAMERA_MAP.get(sheet_num, (1, 7)) #get cameras for given sheet (1 as default)

    # Helper function to check if two frames represent the exact same resting state (look backward)
    def is_same_resting_state(stones_a, stones_b, tol):
        if len(stones_a) != len(stones_b):
            return False
        
        b_remaining = list(stones_b)
        
        # For each stone in A, find its closest matching stone of the same color in B (using greedy appraoch to find closest rock instead of sorting by position due to YOLO jitter)
        for sa in stones_a:
            best_idx = -1
            min_dist = float('inf')
            
            for i, sb in enumerate(b_remaining):
                if sa["color"] == sb["color"]:
                    dist = math.hypot(sa["position"][0] - sb["position"][0], 
                                    sa["position"][1] - sb["position"][1])
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = i
                        
            # If no same-color stone is within tolerance, states don't match
            if best_idx == -1 or min_dist > tol:
                return False
                
            # Remove the matched stone so it can't be double-claimed
            b_remaining.pop(best_idx)
            
        return True

    # Helper function to determine if a frame is unsettled (look foward to see if stones are moving)
    def is_unsettled_frame(curr_stones, next_stones, tol):
        if not next_stones:
            return False
            
        next_remaining = list(next_stones)
        
        # For each stone in current, find its closest matching stone of the same color in next (using greedy as described above)
        for cs in curr_stones:
            best_idx = -1
            min_dist = float('inf')
            
            for i, ns in enumerate(next_remaining):
                if cs["color"] == ns["color"]:
                    dist = math.hypot(cs["position"][0] - ns["position"][0], 
                                    cs["position"][1] - ns["position"][1])
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = i
                        
            # If any stone moved further than tolerance, the frame is unsettled
            if best_idx == -1 or min_dist > tol:
                return True
                
            # Remove the matched stone so it can't be double-claimed
            next_remaining.pop(best_idx)
            
        return False

    pending_start_frame = None
    committed_start_ends = set()

    # Main iteration through all raw frames
    for i in range(len(frames)):
        current = frames[i]
        cam_in_frame = current.get("camera")
        
        # Determine house being shot from and house being shot at based on alternating ends
        if current_end % 2 == 0:
            house_shot_from = cam_house_1
            house_shot_at = cam_house_2
        else:
            house_shot_from = cam_house_2
            house_shot_at = cam_house_1
        active_camera = house_shot_at

        # Discard frames that do not match the target house camera being shot at
        if cam_in_frame != active_camera:
            continue

        stones = current["stones"]
        num_stones = len(stones)
        
        # Handle frames where no stones are detected on the sheet
        if num_stones == 0:
            # Look ahead across the next 2 frames to verify sustained empty board state
            upcoming_zeros = sum(
                1 for k in range(i, min(i + 2, len(frames)))
                  if frames[k].get("camera") in (cam_house_1, cam_house_2) and len(frames[k]["stones"]) == 0)
            
            if max_stones_in_current_end >= 4 and upcoming_zeros >= 2:
                current_end += 1
                current_shot_number = 0
                max_stones_in_current_end = 0
                # Recalculate active camera for the new end immediately
                if current_end % 2 == 0:
                    house_shot_from = cam_house_1
                    house_shot_at = cam_house_2
                else:
                    house_shot_from = cam_house_2
                    house_shot_at = cam_house_1
                active_camera = house_shot_at

            # Keep track of the latest empty frame at the active camera as candidate start frame
            pending_start_frame = current
            continue

        # Check if we need to commit the starting empty frame for the current end before processing stones
        if current_end not in committed_start_ends:
            if pending_start_frame is not None:
                start_frame = pending_start_frame.copy()
            else:
                start_frame = current.copy()
            start_frame["end_num"] = current_end
            if not (parsed_frames and parsed_frames[-1].get("source_filename") == start_frame.get("source_filename")):
                parsed_frames.append(start_frame)
            committed_start_ends.add(current_end)

        # Check if the game is in the teardown/clearing phase (stone count dropping from at least 4 to 0) 
        if max_stones_in_current_end >= 4 and num_stones < max_stones_in_current_end: # might want to change to lower/higher number but 4 seems like a good spot based on youtube feeds
            future_stones = [
                len(frames[k]["stones"]) for k in range(i, len(frames)) 
                if frames[k].get("camera") == active_camera
            ]
            if 0 in future_stones:
                zero_idx = future_stones.index(0)
                clearing_segment = future_stones[:zero_idx + 1]
                # Filter out clearing phase frames if stone counts strictly decrease down to 0, should work as iamges are usually cleared in 1-2 frames
                if len(clearing_segment) > 1 and all(clearing_segment[j] >= clearing_segment[j+1] for j in range(len(clearing_segment) - 1)):
                    continue

        # Track the maximum number of stones observed in the current end
        if num_stones > max_stones_in_current_end:
            max_stones_in_current_end = num_stones

        # Get stones from the immediate next frame for motion check
        next_frame_stones = []
        for k in range(i + 1, len(frames)):
            if frames[k].get("camera") == active_camera:
                next_frame_stones = frames[k]["stones"]
                break
        
        # Skip frames where stones are actively moving (unsettled)
        if is_unsettled_frame(stones, next_frame_stones, yolo_tolerance):
            continue

        # Skip duplicate static frames that match the previous resting state
        if parsed_frames:
            same_end_parsed = [pf for pf in parsed_frames if pf.get("end_num") == current_end and len(pf["stones"]) > 0]
            if same_end_parsed:
                last_accepted_stones = same_end_parsed[-1]["stones"]
                if is_same_resting_state(stones, last_accepted_stones, yolo_tolerance):
                    continue

        # Calc number of shots in this end
        shots_in_this_end = [pf for pf in parsed_frames if pf.get("end_num") == current_end and len(pf["stones"]) > 0]
        current_shot_number = len(shots_in_this_end)

        # Append the successfully filtered stable frame, may have to change this for CV pipeline
        current["end_num"] = current_end
        current["shot_num"] = current_shot_number # not actual confirmed current shot, still have to account for edge cases
        parsed_frames.append(current)
        
    # Ensure any pending start frame for the final active end is committed if not already
    if pending_start_frame is not None and current_end not in committed_start_ends:
        start_frame = pending_start_frame.copy()
        start_frame["end_num"] = current_end
        if not (parsed_frames and parsed_frames[-1].get("source_filename") == start_frame.get("source_filename")):
            parsed_frames.append(start_frame)
        committed_start_ends.add(current_end)

    parsed_frames = post_parse_lookback_and_fix(parsed_frames) #fix edge cases, now should have accurate shots and end nums
    print(f"\nFiltering complete. Retained {len(parsed_frames)} stable frames")

    # --- CONSOLIDATED GAME STATE WARNING ---
    ends_dict = {}
    for pf in parsed_frames:
        end_num = pf.get("end_num", 0)
        if end_num not in ends_dict:
            ends_dict[end_num] = []
        ends_dict[end_num].append(pf)

    total_detected_ends = len(ends_dict)
    total_game_frames = len(parsed_frames)
    expected_total_frames = 8 * 17

    if total_detected_ends != 8 or total_game_frames != expected_total_frames:
        print(f"[GAME STATE WARNING] Structure mismatch: Detected {total_detected_ends} ends "
              f"with {total_game_frames} total frames. Expected 8 ends ({expected_total_frames} frames). "
              f"This discrepancy may be due to an extra end resulting from a tie or missing frame data.")
    
    # Copy qualified JSON to the target output directory 
    for pf in parsed_frames:
        filename = pf.get("source_filename")
        dst_json = json_out / f"{filename}.json"
        src_json = json_in / f"{filename}.json"

        if src_json.exists():
            # Load original raw data for real frames and add calculated fields
            with open(src_json, "r") as jf_in:
                j_data = json.load(jf_in)
            j_data["end_num"] = pf.get("end_num")
            j_data["shot_num"] = pf.get("shot_num")
            j_data["source_filename"] = filename
        else:
            # Synthetic frames do not exist in raw input; use the modified pf dictionary directly
            j_data = pf

        with open(dst_json, "w") as jf_out:
            json.dump(j_data, jf_out, indent=2)

    print(f"Parsed files successfully copied to '{output_dir}/'.")
