import json
import math
import shutil
from pathlib import Path

def post_parse_lookback_and_fix(parsed_frames, single_gap_threshold=22.0, double_gap_threshold=42.0):
    """
    Performs a post-parsing lookback pass for the entire game. Skips ends with >= 17 frames. 
    Detects missing shots using timestamp deltas, injects synthetic frames, and re-indexes shot numbers.
    """
    if not parsed_frames:
        return parsed_frames

    fixed_frames = []
    
    # 1. Group parsed frames by end number
    ends_dict = {}
    for pf in parsed_frames:
        end_num = pf.get("end_num", 0)
        if end_num not in ends_dict:
            ends_dict[end_num] = []
        ends_dict[end_num].append(pf)

    # 2. Process each end independently
    for end_num, frames_in_end in ends_dict.items():
        frames_in_end.sort(key=lambda x: x["time"])
        
        # If the end already has 17 or more frames skip gap analysis entirely
        if len(frames_in_end) >= 17:
            fixed_frames.extend(frames_in_end)
            continue

        rebuilt_end_frames = []
        
        for i in range(len(frames_in_end)):
            current_frame = frames_in_end[i]
            
            if i > 0:
                prev_frame = rebuilt_end_frames[-1]
                time_delta = current_frame["time"] - prev_frame["time"]
                
                # Case A: Two Consecutive Hogged Stones 
                if time_delta >= double_gap_threshold:
                    print(f"[LOOKBACK WARNING] End {end_num}: Large time gap of {time_delta:.1f}s detected "
                          f"between timestamp {prev_frame['time']:.1f}s and {current_frame['time']:.1f}s.")
                    print(f"[LOOKBACK FIX] Injecting 2 synthetic missing frames (Two Hogged Stones case).")
                    
                    t1 = prev_frame["time"] + (time_delta / 3.0) #determine times for injected frams
                    t2 = prev_frame["time"] + (2.0 * time_delta / 3.0)
                    
                    synth_frame_1 = prev_frame.copy() #add synth frames
                    synth_frame_1["time"] = t1
                    synth_frame_1["shot_num"] = len(rebuilt_end_frames) + 1
                    rebuilt_end_frames.append(synth_frame_1)
                    
                    synth_frame_2 = prev_frame.copy()
                    synth_frame_2["time"] = t2
                    synth_frame_2["shot_num"] = len(rebuilt_end_frames) + 1
                    rebuilt_end_frames.append(synth_frame_2)
                
                # Case B: Single Missing Shot (or repalcmemnt knockout)
                elif time_delta >= single_gap_threshold:
                    print(f"[LOOKBACK WARNING] End {end_num}: Time gap of {time_delta:.1f}s detected "
                          f"between timestamp {prev_frame['time']:.1f}s and {current_frame['time']:.1f}s.")
                    print(f"[LOOKBACK FIX] Injecting 1 synthetic missing frame (Single Hog / Replacement case).")
                    
                    t_synth = prev_frame["time"] + (time_delta / 2.0) #determine times for injected frame 
                    
                    synth_frame = prev_frame.copy()
                    synth_frame["time"] = t_synth
                    synth_frame["shot_num"] = len(rebuilt_end_frames) + 1
                    rebuilt_end_frames.append(synth_frame)

            current_frame["shot_num"] = len(rebuilt_end_frames) + 1
            rebuilt_end_frames.append(current_frame)
            
        fixed_frames.extend(rebuilt_end_frames)
        
    return fixed_frames

def parse_curling_frames(input_dir="raw_data", output_dir="parsed_data", yolo_tolerance=2.5):
    # Setup input and output directories for JSON
    json_in = Path(input_dir) / "json"
    json_out = Path(output_dir) / "json"
    json_out.mkdir(parents=True, exist_ok=True)


    print(f"Parsing frames and detecting ends from '{input_dir}'...")

    # Load all sorted frame JSON files from the input directory
    json_files = list(json_in.glob("*.json"))
    frames = []
    for jf in json_files:
        with open(jf, "r") as f:
            frames.append(json.load(f))

    # Guard clause if no frames are found
    if not frames:
        print("No frames found to parse.")
        return

    frames.sort(key=lambda x: x["time"])

    parsed_frames = []
    current_end = 0 #can use this var to add end num to jsons
    current_shot_number = 0 #DONT use this var to add shot num to jsons, backwards edge case code later gives (hopefully) correct final num shot
    max_stones_in_current_end = 0

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

    # Main iteration through all raw frames
    for i in range(len(frames)):
        current = frames[i]
        stones = current["stones"]
        num_stones = len(stones)
        
        # Handle frames where no stones are detected on the sheet
        if num_stones == 0:
            # Look ahead across the next 2 frames to verify sustained empty board state
            upcoming_zeros = sum(1 for k in range(i, min(i + 2, len(frames))) if len(frames[k]["stones"]) == 0)
            
            if max_stones_in_current_end >= 4 and upcoming_zeros >= 2:
                current_end += 1
                current_shot_number = 0
                max_stones_in_current_end = 0
            
            # Keep exactly 1 clean empty frame to mark the start of the new end
            if not (parsed_frames and len(parsed_frames[-1]["stones"]) == 0):
                current["end_num"] = current_end
                parsed_frames.append(current)
            continue

        # Check if the game is in the teardown/clearing phase (stone count dropping from at least 4 to 0) 
        if max_stones_in_current_end >= 4 and num_stones < max_stones_in_current_end: # might want to change to lower/higher number but 4 seems like a good spot based on youtube feeds
            future_stones = [len(frames[k]["stones"]) for k in range(i, len(frames))]
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
        next_frame_stones = frames[i + 1]["stones"] if i + 1 < len(frames) else []
        
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

        #calc number of shots in this end
        shots_in_this_end = [pf for pf in parsed_frames if pf.get("end_num") == current_end and len(pf["stones"]) > 0]
        current_shot_number = len(shots_in_this_end)

        # Append the successfully filtered stable frame, may have to change this for CV pipeline
        current["end_num"] = current_end
        current["shot_num"] = current_shot_number # not actual confirmed current shot, still have to account for edge cases
        parsed_frames.append(current)
        
    parsed_frames = post_parse_lookback_and_fix(parsed_frames) #fix edge cases, now should have accurate shots and end nums
    print(f"\nFiltering complete. Retained {len(parsed_frames)} stable frames")
    
    # Copy qualified JSON to the target output directory (DOESNT WORK!, will have to change this all for CV pipeline anyways so safe to ignore)
    for pf in parsed_frames:
        f_idx = pf["frame_index"]
        filename = f"frame_{f_idx:04d}"
        
        src_json = json_in / f"{filename}.json"
        dst_json = json_out / f"{filename}.json"
        if src_json.exists():
            with open(src_json, "r") as jf_in:
                j_data = json.load(jf_in)
            
            with open(dst_json, "w") as jf_out:
                json.dump(j_data, jf_out, indent=2)

    print(f"Parsed files successfully copied to '{output_dir}/'.")

if __name__ == "__main__":
    parse_curling_frames(input_dir="raw_curling_data", output_dir="parsed_curling_data", yolo_tolerance=2.5)