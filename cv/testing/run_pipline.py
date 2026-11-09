import os
import json
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw


# This file generates some fake data and image generation for parsing testing. To use move into cv/ (same location as parse_stones.py), copy parse_stones.py into section 2, then run.
# Look at raw_curling_data/ and parsed_curling_data/ to compare images and JSONs


# ==========================================
# 1. SIMULATION GENERATOR (8 Ends, 0-Indexed)
# ==========================================
class CurlingSimulation:
    def __init__(self, output_dir="raw_curling_data"):
        self.output_dir = output_dir
        os.makedirs(os.path.join(output_dir, "json"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        
        self.width = 600
        self.height = 600
        self.house_center = (300, 300)
        self.house_radii = [25, 75, 125, 175]
        
    def run_simulation(self):
        current_time = 0.0
        total_ends = 8  # Updated to 8 ends
        
        team_colors = ["green", "yellow"] # Green starts the game
        color_idx = 0 
        
        frame_id = 0
        
        # 0-indexed ends (0 through 7)
        for end in range(total_ends):
            print(f"Simulating End {end}...")
            # Even ends (0, 2, 4, 6): Shoot from Cam 1 -> Target Cam 7
            # Odd ends (1, 3, 5, 7): Shoot from Cam 7 -> Target Cam 1
            if end % 2 == 0:
                source_cam = 1
                target_cam = 7
            else:
                source_cam = 7
                target_cam = 1
            
            house_stones = [] # Accumulated resting stones in the target house for this end
            shots_in_end = 16 # 8 shots per team
            
            for shot in range(shots_in_end):
                color = team_colors[color_idx]
                color_idx = 1 - color_idx # Alternate turns
                
                # Shot timing (~35-42 seconds total per shot interval)
                shot_start = current_time
                planning_duration = random.uniform(25.0, 32.0)
                travel_duration = 6.0 # Time traveling down sheet
                shot_duration = planning_duration + travel_duration
                shot_end = shot_start + shot_duration + random.uniform(2.0, 4.0)
                
                release_time = shot_start + planning_duration
                land_time = release_time + travel_duration
                
                # 5% chance stone is hogged or burnt
                is_hogged = random.random() < 0.05
                
                if not is_hogged:
                    # 50% chance to target near an existing stone to promote knockouts/collisions
                    if house_stones and random.random() < 0.50:
                        target_stone = random.choice(house_stones)
                        angle = random.uniform(0, 2 * math.pi)
                        dist = random.uniform(0, 18) # Land right on/near existing stone
                        target_x = target_stone["position"][0] + dist * math.cos(angle)
                        target_y = target_stone["position"][1] + dist * math.sin(angle)
                    else:
                        angle = random.uniform(0, 2 * math.pi)
                        dist = random.gauss(0, 60)
                        dist = max(0, min(dist, 160))
                        target_x = self.house_center[0] + dist * math.cos(angle)
                        target_y = self.house_center[1] + dist * math.sin(angle)
                        
                    final_pos = [round(target_x, 1), round(target_y, 1)]
                else:
                    final_pos = None 
                
                # Generate camera frames on 6-second ticks across the shot window
                tick = math.ceil(current_time / 6.0) * 6.0
                if tick < current_time:
                    tick += 6.0
                    
                while tick <= shot_end:
                    cam = 1 if int(tick // 6) % 2 == 0 else 7
                    stones_in_frame = []
                    
                    # 1. Source Camera View (House being shot from): Mostly empty, brief stone at release
                    if cam == source_cam:
                        if release_time <= tick <= release_time + 4.0:
                            stones_in_frame.append({
                                "color": color,
                                "position": [round(random.uniform(285, 315), 1), round(random.uniform(520, 560), 1)]
                            })
                    
                    # 2. Target Camera View (House being shot at): Accumulated resting stones + traveling stone
                    elif cam == target_cam:
                        # Include all previously resting stones in this end
                        for s in house_stones:
                            stones_in_frame.append(s)
                            
                        # Include traveling stone if in motion
                        if release_time <= tick <= land_time and not is_hogged:
                            progress = (tick - release_time) / travel_duration
                            progress = max(0.0, min(1.0, progress))
                            start_x, start_y = 300.0, 600.0
                            curr_x = start_x + (final_pos[0] - start_x) * progress
                            curr_y = start_y + (final_pos[1] - start_y) * progress
                            stones_in_frame.append({
                                "color": color,
                                "position": [round(curr_x, 1), round(curr_y, 1)]
                            })

                    frame_data = {
                        "camera": cam,
                        "time": round(tick, 1),
                        "stones": stones_in_frame
                    }
                    
                    self._save_frame(frame_id, frame_data)
                    frame_id += 1
                    tick += 6.0
                
                # After shot settles, add to house stones with robust collision/knockout handling
                if not is_hogged and final_pos is not None:
                    new_stone = {"color": color, "position": final_pos}
                    house_stones = self._resolve_collisions_and_knockouts(new_stone, house_stones)
                
                current_time = shot_end
                
        print(f"Simulation complete! Generated {frame_id} raw frames in '{self.output_dir}/'.")

    def _resolve_collisions_and_knockouts(self, new_stone, existing_stones):
        """Resolves collisions and simulates realistic knockouts/displacements."""
        min_dist = 24.0
        updated_stones = []
        
        for stone in existing_stones:
            dx = new_stone["position"][0] - stone["position"][0]
            dy = new_stone["position"][1] - stone["position"][1]
            dist = math.hypot(dx, dy)
            
            if dist < min_dist:
                # Knockout / displacement physics: push existing stone outward
                angle = math.atan2(dy, dx)
                push_dist = min_dist * 1.3
                new_x = stone["position"][0] - push_dist * math.cos(angle)
                new_y = stone["position"][1] - push_dist * math.sin(angle)
                
                # Keep within house bounds
                new_x = max(100, min(new_x, 500))
                new_y = max(100, min(new_y, 500))
                
                updated_stones.append({
                    "color": stone["color"],
                    "position": [round(new_x, 1), round(new_y, 1)]
                })
            else:
                updated_stones.append(stone)
                
        updated_stones.append(new_stone)
        return updated_stones

    def _save_frame(self, frame_id, data):
        json_path = os.path.join(self.output_dir, "json", f"frame_{frame_id:04d}.json")
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
            
        img = Image.new("RGB", (self.width, self.height), color="#EAEAEA")
        draw = ImageDraw.Draw(img)
        
        hx, hy = self.house_center
        ring_colors = ["#FFFFFF", "#0055A5", "#FFFFFF", "#EF3340"]
        for r, col in zip(reversed(self.house_radii), reversed(ring_colors)):
            draw.ellipse([hx - r, hy - r, hx + r, hy + r], fill=col, outline="#CCCCCC")
            
        draw.line([0, hy, self.width, hy], fill="#999999", width=2)
        draw.line([hx, 0, hx, self.height], fill="#999999", width=2)
        
        for stone in data["stones"]:
            sx, sy = stone["position"]
            radius = 12
            fill_col = "#2E8B57" if stone["color"] == "green" else "#FFD700"
            outline_col = "#000000"
            draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius], fill=fill_col, outline=outline_col, width=2)
            
        draw.text((10, 10), f"Camera: {data['camera']} | Time: {data['time']}s", fill="#333333")
        
        img_path = os.path.join(self.output_dir, "images", f"frame_{frame_id:04d}.png")
        img.save(img_path)


# ==========================================
# 2. GIVEN CODE (UNTOUCHED)
# ==========================================

# Add parse_stones.py code here. yes it is stupid, i am sorry...

# ==========================================
# 3. PIPELINE EXECUTION & IMAGE ORGANIZATION
# ==========================================
def run_pipeline():
    input_base = "raw_curling_data"
    output_base = "parsed_curling_data"
    
    print("--- Step 1: Generating Raw Simulation Data ---")
    sim = CurlingSimulation(output_dir=input_base)
    sim.run_simulation()
    
    print("\n--- Step 2: Parsing Frames with parse_stones logic ---")
    parse_curling_frames(input_dir=input_base, output_dir=output_base, sheet_num=1, yolo_tolerance=2.5)
    
    print("\n--- Step 3: Organizing Output Images ---")
    output_images_dir = Path(output_base) / "images"
    output_images_dir.mkdir(parents=True, exist_ok=True)
    
    parsed_json_dir = Path(output_base) / "json"
    raw_images_dir = Path(input_base) / "images"
    
    copied_count = 0
    for json_file in parsed_json_dir.glob("*.json"):
        stem = json_file.stem
        if "_synth_" in stem:
            base_stem = stem.split("_synth_")[0]
            src_img = raw_images_dir / f"{base_stem}.png"
        else:
            src_img = raw_images_dir / f"{stem}.png"
            
        dst_img = output_images_dir / f"{stem}.png"
        if src_img.exists():
            image_data = Image.open(src_img)
            image_data.save(dst_img)
            copied_count += 1
            
    print(f"Successfully organized {copied_count} corresponding images into '{output_base}/images/'.")
    print(f"\nPipeline finished successfully!\n- Input folder: {input_base}/ (contains 'json/' and 'images/')\n- Output folder: {output_base}/ (contains 'json/' and 'images/')")

if __name__ == "__main__":
    run_pipeline()