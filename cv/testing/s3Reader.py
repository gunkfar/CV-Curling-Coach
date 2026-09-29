import os
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import boto3
from dotenv import load_dotenv
import random

# Load environment variables from .env
load_dotenv()

ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

class ImageReviewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("S3 / R2 Image Scanner & Downloader")
        self.root.geometry("900x700")

        # Initialize S3 client for Cloudflare R2
        self.s3_client = boto3.client(
            service_name='s3',
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY
        )

        self.image_keys = []
        self.current_index = 0
        self.current_image_bytes = None

        self._build_gui()
        self._load_bucket_file_list()

    def _build_gui(self):
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        self.info_label = ttk.Label(toolbar, text="Loading bucket contents...", font=("Arial", 11))
        self.info_label.pack(side=tk.LEFT)

        # Image canvas / display area
        self.image_label = ttk.Label(self.root, text="No image loaded", anchor="center")
        self.image_label.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Bottom control panel
        controls = ttk.Frame(self.root, padding=10)
        controls.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_prev = ttk.Button(controls, text="◀ Previous", command=self.show_previous, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=5)

        self.btn_next = ttk.Button(controls, text="Next ▶", command=self.show_next, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT, padx=5)

        self.btn_download = ttk.Button(controls, text="💾 Save to Folder", command=self.download_current_image, state=tk.DISABLED)
        self.btn_download.pack(side=tk.RIGHT, padx=5)

    def _load_bucket_file_list(self):
        """
        TIMESTAMP JUMP SAMPLING:
        Uses the 'camer10_YYYYMMDD_HHMMSS' format to jump directly to a random 
        camera, date, and hour across the entire bucket in 1 API call.
        """
        MAX_IMAGES = 50
        
        # Generate a random camera + timestamp target
        rand_cam = f"camera{random.randint(1, 10)}"           # Picks a camera (e.g. camera1 to camera10)
        rand_year = random.choice(["2025", "2026"])            # Adjust years if needed
        rand_month = f"{random.randint(1, 12):02d}"
        rand_day = f"{random.randint(1, 28):02d}"
        rand_hour = f"{random.randint(0, 23):02d}"
        
        # Target string e.g., 'camera4_20260315_14'
        random_target = f"{rand_cam}_{rand_year}{rand_month}{rand_day}_{rand_hour}"
        
        print(f"Jumping to random date/time in bucket: '{random_target}'...")

        try:
            # Tell S3 to skip straight to files after this random target
            response = self.s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                StartAfter=random_target,
                MaxKeys=100
            )

            # Fallback if the target jumped past the very last file in the bucket
            if 'Contents' not in response or not response['Contents']:
                print("Target was near end of bucket; starting from top.")
                response = self.s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    MaxKeys=100
                )

            found_keys = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.lower().endswith(VALID_EXTENSIONS):
                        found_keys.append(key)

            if not found_keys:
                self.info_label.config(text="No images found.")
                return

            # Pick 50 images from this random spot
            sample_size = min(MAX_IMAGES, len(found_keys))
            self.image_keys = found_keys[:MAX_IMAGES]

            print(f"Loaded {len(self.image_keys)} random images starting around '{random_target}'!")
            self.info_label.config(text=f"Loaded {len(self.image_keys)} random images.")
            self.show_image(0)

        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to list bucket contents:\n{e}")
            self.info_label.config(text="Error connecting to S3/R2.")
            print(f"Error: {e}")

    def show_image(self, index):
        if not (0 <= index < len(self.image_keys)):
            return

        self.current_index = index
        key = self.image_keys[index]
        self.info_label.config(text=f"[{index + 1} / {len(self.image_keys)}] {key}")

        try:
            # Read single object into memory
            response = self.s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            self.current_image_bytes = response['Body'].read()

            # Process with PIL
            img = Image.open(io.BytesIO(self.current_image_bytes))
            
            # Resize image to fit window maintaining aspect ratio
            img.thumbnail((800, 550), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)

            self.image_label.config(image=tk_img, text="")
            self.image_label.image = tk_img  # Keep reference to avoid garbage collection

            # Update button states
            self.btn_prev.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
            self.btn_next.config(state=tk.NORMAL if index < len(self.image_keys) - 1 else tk.DISABLED)
            self.btn_download.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image '{key}':\n{e}")

    def show_previous(self):
        if self.current_index > 0:
            self.show_image(self.current_index - 1)

    def show_next(self):
        if self.current_index < len(self.image_keys) - 1:
            self.show_image(self.current_index + 1)

    def download_current_image(self):
        if not self.image_keys or self.current_index >= len(self.image_keys):
            return

        # Explicitly target cv/testing/downloaded_images relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        save_dir = os.path.join(script_dir, "downloaded_images")
        os.makedirs(save_dir, exist_ok=True)

        # Extract original filename and build destination path
        key = self.image_keys[self.current_index]
        filename = os.path.basename(key)
        save_path = os.path.join(save_dir, filename)

        try:
            with open(save_path, 'wb') as f:
                f.write(self.current_image_bytes)
            print(f"Saved: {save_path}")
            messagebox.showinfo("Saved!", f"Image saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageReviewApp(root)
    root.mainloop()
