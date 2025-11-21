# convert_compress_script.py

A compact, cross-platform utility to convert common image formats (JPEG, PNG, TIFF, BMP) to WebP and to compress existing WebP images using the `cwebp` command-line tool. The script applies EXIF orientation before conversion, so portrait images keep the correct rotation in the produced WebP files.

**Location**: `convert_compress_script.py` (same folder)

---

## Features

- Recursively finds images under an input directory (default: `images`).
- Applies EXIF orientation (via Pillow) to ensure pixels are upright before conversion.
- Converts non-WebP images to `.webp` using `cwebp` and removes the original file on success.
- Compresses existing `.webp` files with configurable `cwebp` parameters.
- Supports parallel processing with configurable worker count.

---

## Requirements

- Python 3.7+
- Pillow (for EXIF orientation and optional image processing)
- `cwebp` (part of libwebp) — required unless you modify the script to use Pillow to write WebP directly.

A minimal `requirements.txt` is included in this folder (contains `Pillow>=9.0.0`).

### Installing Python dependencies

Windows (cmd.exe / PowerShell) and macOS/Linux (bash/zsh):

```bash
python -m pip install --upgrade pip
python -m pip install -r "./requirements.txt"
```

Replace the path to `requirements.txt` if you run the command from a different working directory.

### Installing `cwebp`

`cwebp` is provided by the libwebp project. Below are common install options by OS; package names may vary by distribution/version.

- macOS (Homebrew):

```bash
brew install webp
```

- Debian / Ubuntu:

```bash
sudo apt update
sudo apt install webp
```

- Fedora / RHEL (dnf):

```bash
sudo dnf install libwebp-tools
```

- Windows:

  - Preferred: download official builds from Google and add the folder containing `cwebp.exe` to your `PATH`:
    https://developers.google.com/speed/webp/download
  - Alternative (package managers):
    - Chocolatey: `choco install webp` (if available on your machine)
    - Scoop: look for a `webp` bucket or place `cwebp.exe` in a folder on `PATH`

Verify `cwebp` is available:

```bash
cwebp -version
```

---

## Usage

Run the script from its folder or supply the full path. The script accepts command-line options to control compression.

Examples (Windows `cmd.exe` and macOS/Linux `bash` examples):

- Default run (uses `images` directory):

```cmd
python convert_compress_script.py
```

- Set quality and method:

```bash
python convert_compress_script.py --quality 75 --method 5
```

- Disable `-sharp_yuv`:

```bash
python convert_compress_script.py --no-sharp-yuv
```

- Pass additional raw `cwebp` args (example: reduce alpha quality):

```bash
python convert_compress_script.py --cwebp-args "--alpha_q 60"
```

- Use a custom input folder and 4 workers:

```bash
python convert_compress_script.py --input-dir path/to/my/images --workers 4
```

Available CLI options (summary):

- `--input-dir`: Directory to search for images (default: `images`).
- `--quality`: `cwebp` quality value 0–100 (default: 85).
- `--method`: `cwebp` method 0–6 (default: 6).
- `--no-sharp-yuv`: Disable the `-sharp_yuv` flag.
- `--cwebp-args`: Additional raw arguments passed to `cwebp` (quote the string if it contains spaces).
- `--workers`: Number of worker threads (0 uses `os.cpu_count()`).

---

## What to expect

- The script will print progress messages for each file it converts or compresses.
- Non-WebP files are converted to `.webp` and the original files are removed upon successful conversion.
- If Pillow is present, EXIF orientation is applied — this prevents portrait images from being rotated incorrectly in the output.

---

## Troubleshooting

- Output images rotated 90° or upside-down:
  - Ensure Pillow is installed (the script prints messages if Pillow is not available).
  - Ensure `cwebp` is on `PATH` and is being invoked successfully.
  - Some viewers honor EXIF tags while WebP viewers may not — the script transposes pixels to remove reliance on EXIF tags.

- `cwebp` not found or errors invoking it:
  - Add the folder containing `cwebp`/`cwebp.exe` to your `PATH`.
  - On Windows, open a new terminal after changing PATH.
  - Verify with `cwebp -version`.

- Temporary `.oriented.*` files remain after running:
  - That indicates the script failed before it could clean up temporary files. Check stderr output from the script for details.

---

## CI / Automation tips

- Install Python dependencies in your CI pipeline using the `requirements.txt` included.
- Install `cwebp` using the platform package manager available in the runner (Homebrew on macOS, `apt` on Ubuntu, etc.).
- Run the script as part of an asset build step to convert/compress images before deployment.

Example (GitHub Actions step snippet):

```yaml
- name: Install libwebp (Ubuntu)
  run: sudo apt-get update && sudo apt-get install -y webp

- name: Install Python deps
  run: python -m pip install -r ./public/requirements.txt

- name: Convert images
  run: python ./public/convert_compress_script.py --input-dir ./public/images
```

---
