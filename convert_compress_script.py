import os
import concurrent.futures
import subprocess
import argparse
import shlex
try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

# Set the directory containing images (default)
INPUT_DIR = "images"

# Defaults for WebP compression settings
QUALITY = 85  # Adjust for balance between size and quality
METHOD = 6     # Compression method (higher = better but slower)

SUPPORTED_FORMATS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".heic", ".heif")

# Runtime configuration populated from CLI args
CONFIG = {}

def auto_orient(image_path):
    """Apply EXIF orientation so portrait images keep correct orientation.

    This uses Pillow's ImageOps.exif_transpose to rotate/flip the image
    according to its EXIF Orientation tag, then saves the file back.
    If Pillow is not installed, this is a no-op.
    """
    if Image is None or ImageOps is None:
        print(f"[auto_orient] Pillow not available; skipping orientation for: {image_path}")
        return
    try:
        with Image.open(image_path) as img:
            exif = None
            try:
                exif = img.getexif()
            except Exception:
                exif = None

            orientation = None
            try:
                if exif:
                    orientation = exif.get(274)  # 274 is the Orientation tag
            except Exception:
                orientation = None

            print(f"[auto_orient] Processing: {image_path} | format={img.format} | EXIF Orientation={orientation}")

            oriented = ImageOps.exif_transpose(img)

            # If orientation tag was present or the transposed image differs, save result
            try:
                different = oriented.size != img.size or oriented.mode != img.mode
            except Exception:
                different = True

            if orientation or different:
                fmt = img.format or os.path.splitext(image_path)[1].lstrip('.').upper()
                save_kwargs = {}
                if fmt == 'JPEG':
                    save_kwargs['quality'] = 95
                oriented.save(image_path, format=fmt, **save_kwargs)
                print(f"[auto_orient] Oriented and saved: {image_path}")
            else:
                print(f"[auto_orient] No orientation change needed: {image_path}")
    except Exception as e:
        print(f"[auto_orient] Error processing {image_path}: {e}")
        return

def compress_webp(image_path):
    """Compress an existing WebP image using cwebp with optimal settings."""
    # Build cwebp command from CONFIG with sensible defaults
    quality = CONFIG.get("quality", QUALITY)
    method = CONFIG.get("method", METHOD)
    sharp = CONFIG.get("sharp_yuv", True)
    extra = CONFIG.get("cwebp_args", "") or ""
    scale = CONFIG.get("scale", 1.0)

    # If scale < 1.0, we need to downscale the WebP image first using Pillow
    if scale < 1.0 and Image is not None:
        try:
            with Image.open(image_path) as img:
                original_size = img.size
                new_width = int(img.width * scale)
                new_height = int(img.height * scale)
                
                # Ensure dimensions are at least 1x1
                new_width = max(1, new_width)
                new_height = max(1, new_height)
                
                # Use high-quality Lanczos resampling for downscaling
                resized = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Save directly as WebP with Pillow (avoids cwebp subprocess)
                save_kwargs = {
                    'format': 'WEBP',
                    'quality': quality,
                    'method': method
                }
                resized.save(image_path, **save_kwargs)
                print(f"✔ Compressed & scaled: {image_path} ({original_size[0]}x{original_size[1]} → {new_width}x{new_height})")
                return
        except Exception as e:
            print(f"[compress_webp] Pillow resize failed for {image_path}: {e}, falling back to cwebp")
    
    # Original cwebp subprocess path (for scale=1.0 or if Pillow unavailable)
    command = ["cwebp", image_path, "-q", str(quality), "-m", str(method)]
    if sharp:
        command.append("-sharp_yuv")
    if extra:
        try:
            command.extend(shlex.split(extra))
        except Exception:
            # fallback: append raw string (may fail if contains spaces)
            command.append(extra)
    command.extend(["-o", image_path])

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✔ Compressed: {image_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error compressing {image_path}: {e}")

def convert_to_webp(image_path):
    """Convert non-WebP images (JPG, PNG, etc.) to WebP and compress them."""
    # Prefer to apply EXIF orientation in-memory (via Pillow) and give cwebp
    # an oriented temporary file to ensure the output WebP has correct rotation.
    base = os.path.splitext(image_path)[0]
    webp_path = base + ".webp"
    scale = CONFIG.get("scale", 1.0)

    temp_input = image_path
    temp_created = False

    if Image is not None and ImageOps is not None:
        try:
            with Image.open(image_path) as img:
                oriented = ImageOps.exif_transpose(img)
                if oriented.mode not in ("RGB", "RGBA"):
                    oriented = oriented.convert("RGB")
                
                original_size = oriented.size
                
                # Apply downscaling if scale < 1.0
                if scale < 1.0:
                    new_width = int(oriented.width * scale)
                    new_height = int(oriented.height * scale)
                    
                    # Ensure dimensions are at least 1x1
                    new_width = max(1, new_width)
                    new_height = max(1, new_height)
                    
                    # Use high-quality Lanczos resampling for downscaling
                    oriented = oriented.resize((new_width, new_height), Image.LANCZOS)
                    print(f"[convert_to_webp] Scaled: {image_path} ({original_size[0]}x{original_size[1]} → {new_width}x{new_height})")

                # Choose a safe temporary format that cwebp accepts
                if img.format and img.format.upper() == 'PNG':
                    temp_input = base + ".oriented.png"
                    oriented.save(temp_input, format='PNG')
                else:
                    temp_input = base + ".oriented.jpg"
                    oriented.save(temp_input, format='JPEG', quality=95)

                temp_created = True
        except Exception as e:
            print(f"[convert_to_webp] Pillow orientation failed for {image_path}: {e}")
            temp_input = image_path

    # Build cwebp command using runtime CONFIG
    quality = CONFIG.get("quality", QUALITY)
    method = CONFIG.get("method", METHOD)
    sharp = CONFIG.get("sharp_yuv", True)
    extra = CONFIG.get("cwebp_args", "") or ""

    command = ["cwebp", temp_input, "-q", str(quality), "-m", str(method)]
    if sharp:
        command.append("-sharp_yuv")
    if extra:
        try:
            command.extend(shlex.split(extra))
        except Exception:
            command.append(extra)
    command.extend(["-o", webp_path])

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"🔄 Converted: {image_path} → {webp_path}")
        try:
            os.remove(image_path)  # Remove original file after conversion
        except Exception:
            pass
    except subprocess.CalledProcessError as e:
        print(f"❌ Error converting {image_path}: {e}")
    finally:
        if temp_created and temp_input != image_path:
            try:
                os.remove(temp_input)
            except Exception:
                pass

def find_images(directory):
    """Recursively find all images in the directory and subdirectories."""
    images = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".webp") or file.lower().endswith(SUPPORTED_FORMATS):
                images.append(os.path.join(root, file))
    return images

def process_image(image_path):
    """Determine whether to compress or convert an image."""
    if image_path.lower().endswith(".webp"):
        compress_webp(image_path)
    else:
        convert_to_webp(image_path)

def main():
    parser = argparse.ArgumentParser(description="Convert and compress images to WebP with optional cwebp parameters")
    parser.add_argument("--input-dir", default=INPUT_DIR, help="Directory containing images")
    parser.add_argument("--quality", type=int, default=QUALITY, help="cwebp quality (0-100)")
    parser.add_argument("--method", type=int, default=METHOD, help="cwebp method (0-6)")
    parser.add_argument("--no-sharp-yuv", dest="sharp_yuv", action="store_false", help="Disable -sharp_yuv flag")
    parser.add_argument("--cwebp-args", default="", help="Additional raw arguments to pass to cwebp (quoted)")
    parser.add_argument("--workers", type=int, default=0, help="Number of worker threads (0 = os.cpu_count())")
    parser.add_argument("--scale", type=float, default=1.0, help="Downscale factor (0.0-1.0). E.g., 0.5 = 50%% resolution. Default: 1.0 (no scaling)")

    args = parser.parse_args()
    
    # Validate scale parameter
    if args.scale <= 0.0 or args.scale > 1.0:
        parser.error("--scale must be between 0.0 (exclusive) and 1.0 (inclusive)")

    # Populate runtime CONFIG used by worker functions
    CONFIG.update({
        "input_dir": args.input_dir,
        "quality": args.quality,
        "method": args.method,
        "sharp_yuv": args.sharp_yuv,
        "cwebp_args": args.cwebp_args,
        "workers": args.workers or (os.cpu_count() or 1),
        "scale": args.scale,
    })

    images = find_images(CONFIG.get("input_dir", INPUT_DIR))

    if not images:
        print("No images found.")
        return

    scale_info = f" (scale={CONFIG['scale']})" if CONFIG['scale'] < 1.0 else ""
    print(f"Found {len(images)} images. Processing with {CONFIG['workers']} workers{scale_info}...")

    # Use multi-threading to speed up compression and conversion
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["workers"]) as executor:
        executor.map(process_image, images)

    print("✅ All images processed!")

if __name__ == "__main__":
    main()
