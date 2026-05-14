"""
update_sheet_with_images.py
============================
Uploads PNG screenshots to catbox.moe and writes =IMAGE() formulas
into columns J (Page URL) and K (Screenshot) of the Google Sheet.

Usage:
    python update_sheet_with_images.py

Requires:
    - credentials.json in the same folder as this script
    - PNG screenshots placed in UX Audit/screenshots/
"""

import gspread
import subprocess
import os

# ── Config ──
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_URL  = 'https://docs.google.com/spreadsheets/d/1dYj9RUoNNPSyGjJ_A9yP5AFsM4i1SQB3y9M0drY45tg/edit?usp=sharing'

# ── Use relative screenshots folder (local to project) ──
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR        = os.path.join(SCRIPT_DIR, '..', 'screenshots')  # UX Audit/screenshots/
DEFAULT_PAGE_URL = "https://www.girnarsoft.com/"


def upload_to_catbox(filepath):
    print(f"Uploading {os.path.basename(filepath)}...")
    cmd = ["curl", "-s", "-F", "reqtype=fileupload", "-F", f"fileToUpload=@{filepath}", "https://catbox.moe/user/api.php"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.startswith("http"):
        return result.stdout.strip()
    print(f"Failed to upload: {result.stdout}")
    return None


def main():
    if not os.path.isdir(IMAGE_DIR):
        print(f"⚠️  Screenshots folder not found: {IMAGE_DIR}")
        print("    Create 'UX Audit/screenshots/' and place PNGs there first.")
        return

    image_files = sorted([f for f in os.listdir(IMAGE_DIR) if f.endswith('.png')])
    if not image_files:
        print("❌ No PNG images found in screenshots folder!")
        return

    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.sheet1

    # Update Headers
    worksheet.update_acell('J1', 'Referenced Page')
    worksheet.update_acell('K1', 'Screenshot')

    j_col_data = []
    k_col_data = []

    for i in range(10):
        img_idx  = i % len(image_files)
        img_path = os.path.join(IMAGE_DIR, image_files[img_idx])
        img_url  = upload_to_catbox(img_path)
        formula  = f'=IMAGE("{img_url}")' if img_url else ""
        j_col_data.append([DEFAULT_PAGE_URL])
        k_col_data.append([formula])

    print("Writing URLs to Google Sheet...")
    worksheet.update(values=j_col_data, range_name='J2:J11')

    print("Writing IMAGES to Google Sheet...")
    worksheet.update(values=k_col_data, range_name='K2:K11', raw=False)

    print("✅ Done! Check your Google Sheet.")


if __name__ == "__main__":
    main()
