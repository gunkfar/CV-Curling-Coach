import os
import random
import math
from PIL import Image, ImageDraw, ImageChops

# --- CONFIGURATION ---
WIDTH = 225
HEIGHT = 475
STONE_RADIUS = 8  # Total outer radius (16px bounding box)

# Colors
COLOR_ICE = "#F4F7F9"
COLOR_WASHED_GOLD = "#E6D080"
COLOR_WASHED_GREEN = "#A0C5A0"
COLOR_WHITE = "#FFFFFF"

COLOR_YELLOW_STONE = "#FFD700"
COLOR_GREEN_STONE = "#228B22"
COLOR_GRANITE_OUTER = "#7D8488"

OUTPUT_DIR = "curling_samples"

def setup_directory():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

# --- FAST GRAIN & VIGNETTE CACHING ---
def create_vignette_mask(width, height, strength=0.30):
    """Pre-computes radial vignette mask (darker corners/edges)."""
    cx, cy = width / 2.0, height / 2.0
    max_dist = math.hypot(cx, cy)
    pixels = []
    
    for y in range(height):
        for x in range(width):
            dist = math.hypot(x - cx, y - cy) / max_dist
            factor = int(255 * (1.0 - strength * (dist ** 2)))
            pixels.append(factor)
            
    mask = Image.new("L", (width, height))
    mask.putdata(pixels)
    return Image.merge("RGB", (mask, mask, mask))

def build_overlay_cache(width, height, count=10, noise_level=14):
    """Pre-generates a pool of combined Vignette + Grain overlays."""
    vignette = create_vignette_mask(width, height)
    cache = []
    
    for _ in range(count):
        noise_bytes = bytes([
            max(0, min(255, 128 + random.randint(-noise_level, noise_level)))
            for _ in range(width * height * 3)
        ])
        noise_img = Image.frombytes("RGB", (width, height), noise_bytes)
        combined_overlay = ImageChops.multiply(vignette, noise_img)
        cache.append(combined_overlay)
        
    return cache

# --- DRAWING FUNCTIONS ---
def draw_house(draw, center_y, is_top):
    center_x = WIDTH / 2.0
    house_radius = 100
    
    if is_top:
        color_outer = COLOR_WASHED_GREEN
        color_inner = COLOR_WASHED_GOLD
    else:
        color_outer = COLOR_WASHED_GOLD
        color_inner = COLOR_WASHED_GREEN
    
    # Rings
    draw.ellipse([center_x - house_radius, center_y - house_radius, 
                  center_x + house_radius, center_y + house_radius], fill=color_outer)
    
    r8 = house_radius * (8/12)
    draw.ellipse([center_x - r8, center_y - r8, center_x + r8, center_y + r8], fill=COLOR_WHITE)
    
    r4 = house_radius * (4/12)
    draw.ellipse([center_x - r4, center_y - r4, center_x + r4, center_y + r4], fill=color_inner)
    
    r1 = house_radius * (1/12)
    draw.ellipse([center_x - r1, center_y - r1, center_x + r1, center_y + r1], fill=COLOR_WHITE)
    
    # Lines
    draw.line([center_x, 0, center_x, HEIGHT], fill="#E0E5E8", width=1)
    draw.line([0, center_y, WIDTH, center_y], fill="#E0E5E8", width=1)

def draw_stone(draw, x, y, cap_color):
    # 1. Outer granite body
    draw.ellipse([x - STONE_RADIUS, y - STONE_RADIUS, 
                  x + STONE_RADIUS, y + STONE_RADIUS], 
                 fill=COLOR_GRANITE_OUTER, outline="#404040", width=1)
    
    # 2. Centered inner cap
    cap_radius = 5.0
    draw.ellipse([x - cap_radius, y - cap_radius, 
                  x + cap_radius, y + cap_radius], 
                 fill=cap_color, outline="#202020", width=1)

def resolve_collisions(new_stone, existing_stones):
    """
    17.0px min distance eliminates Pillow outline pixel overlap.
    Combines ALL stones (shooter + resting) into a multi-pass relaxation 
    loop so zero visual overlaps occur.
    """
    min_dist = (STONE_RADIUS * 2) + 1.0  # 17.0px guarantees zero border pixel overlap
    nx, ny, n_color = new_stone

    # Step 1: Initial impact momentum from incoming throw
    for i in range(len(existing_stones)):
        ex, ey, e_color = existing_stones[i]
        dx = ex - nx
        dy = ey - ny
        dist = math.hypot(dx, dy)

        if dist < min_dist:
            if dist == 0:
                dx, dy, dist = 0.1, 0.1, math.hypot(0.1, 0.1)

            overlap = min_dist - dist
            dir_x = dx / dist
            dir_y = dy / dist

            # Knock target stone away with substantial force
            impact_force = overlap + random.uniform(25.0, 50.0)
            existing_stones[i] = [ex + dir_x * impact_force, ey + dir_y * impact_force, e_color]

            # Rebound shooter slightly
            new_stone[0] -= dir_x * (overlap * 0.4)
            new_stone[1] -= dir_y * (overlap * 0.4)

    # Step 2: Combine shooter AND existing stones into a single list for multi-pass relaxation
    all_stones = [new_stone] + existing_stones

    for _ in range(10):
        any_overlap = False
        for i in range(len(all_stones)):
            for j in range(i + 1, len(all_stones)):
                x1, y1, c1 = all_stones[i]
                x2, y2, c2 = all_stones[j]

                dx = x2 - x1
                dy = y2 - y1
                dist = math.hypot(dx, dy)

                if dist < min_dist:
                    if dist == 0:
                        dx, dy, dist = 0.1, 0.1, math.hypot(0.1, 0.1)

                    any_overlap = True
                    overlap = min_dist - dist
                    dir_x = dx / dist
                    dir_y = dy / dist

                    # Push secondary stone clear of collision
                    push_dist = overlap + random.uniform(8.0, 20.0)
                    all_stones[j] = [x2 + dir_x * push_dist, y2 + dir_y * push_dist, c2]

        if not any_overlap:
            break

    # Write back updated coordinates
    new_stone[0], new_stone[1], new_stone[2] = all_stones[0]
    for idx in range(len(existing_stones)):
        existing_stones[idx] = all_stones[idx + 1]

def is_partially_visible(x, y):
    """Checks if a stone is at least partially visible on the sheet."""
    return (-STONE_RADIUS <= x <= WIDTH + STONE_RADIUS) and (-STONE_RADIUS <= y <= HEIGHT + STONE_RADIUS)

def generate_club_shot_target(is_top, house_center_y):
    """
    Models Club Curler Shot Mechanics (~60% execution accuracy):
    - Good line control (stays mostly within sheet width).
    - Frequent weight errors (too heavy -> past house/off back, too light -> short guard).
    - Occasional wide miss (~4% chance).
    """
    roll = random.random()
    
    if roll < 0.04:
        aim_x = random.choice([-10, WIDTH + 10])
    else:
        aim_x = random.gauss(WIDTH / 2.0, 28)
        
    if roll < 0.55:
        weight_error = random.gauss(0, 38)
        aim_y = house_center_y + weight_error
    elif roll < 0.88:
        offset = 120 if is_top else -120
        aim_y = random.gauss(house_center_y + offset, 30)
    else:
        offset = 200 if is_top else -200
        aim_y = random.gauss(house_center_y + offset, 40)
        
    return aim_x, aim_y

def generate_dataset():
    setup_directory()
    
    print("Pre-computing grain & vignette overlays...")
    overlay_cache = build_overlay_cache(WIDTH, HEIGHT, count=10)
    
    total_images_generated = 0
    NUM_GAMES = 5
    ENDS_PER_GAME = 8
    STONES_PER_TEAM = 8  # 16 total throws per end
    
    for game in range(1, NUM_GAMES + 1):
        for end in range(1, ENDS_PER_GAME + 1):
            stones_on_ice = []
            
            is_top = (end % 2 != 0)
            house_center_y = 125 if is_top else (HEIGHT - 125)
            yellow_starts = (end % 2 != 0)
            
            for throw in range(1, (STONES_PER_TEAM * 2) + 1):
                if yellow_starts:
                    current_color = COLOR_YELLOW_STONE if throw % 2 != 0 else COLOR_GREEN_STONE
                else:
                    current_color = COLOR_GREEN_STONE if throw % 2 != 0 else COLOR_YELLOW_STONE
                
                aim_x, aim_y = generate_club_shot_target(is_top, house_center_y)
                new_stone = [aim_x, aim_y, current_color]
                
                # Resolve collisions against existing stones BEFORE deciding if shooter stays on screen
                resolve_collisions(new_stone, stones_on_ice)
                
                # Add shooter if visible
                if is_partially_visible(new_stone[0], new_stone[1]):
                    stones_on_ice.append(new_stone)
                
                # Remove any stones knocked off-screen
                initial_count = len(stones_on_ice)
                stones_on_ice = [s for s in stones_on_ice if is_partially_visible(s[0], s[1])]
                knocked_off_count = initial_count - len(stones_on_ice)
                
                # --- DRAW IMAGE ---
                img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_ICE)
                draw = ImageDraw.Draw(img)
                
                draw_house(draw, house_center_y, is_top)
                
                for sx, sy, color in stones_on_ice:
                    draw_stone(draw, sx, sy, color)
                
                # Apply pre-computed Grain & Vignette
                overlay = random.choice(overlay_cache)
                final_img = ImageChops.soft_light(img, overlay)
                
                total_images_generated += 1
                filename = f"game{game}_end{end}_throw{throw:02d}.png"
                final_img.save(os.path.join(OUTPUT_DIR, filename))
                
                log_extra = ""
                if knocked_off_count > 0:
                    log_extra += f" [{knocked_off_count} stone(s) KNOCKED OFF]"
                    
                print(f"Generated {total_images_generated}/640: {filename}{log_extra}")

if __name__ == "__main__":
    print("Starting dataset generation...")
    generate_dataset()
    print(f"Finished! All images saved to '{OUTPUT_DIR}'.")