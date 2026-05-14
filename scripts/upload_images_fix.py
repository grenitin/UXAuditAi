"""
upload_images_fix.py
=====================
Fixes the Screenshot column in existing audit CSVs by:
1. Uploading local PNG screenshots to catbox.moe
2. Injecting =IMAGE(url) formulas back into the CSV

Usage:
    python upload_images_fix.py

Requires:
    - CarDekho and BikeDekho CSV files in the 'UX Audit/' folder
    - PNG screenshots placed in the 'screenshots/' folder next to this script
"""

import os
import subprocess
import pandas as pd

# ── Paths (relative to script location) ──
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(SCRIPT_DIR, '..', 'screenshots')  # UX Audit/screenshots/
AUDIT_DIR     = os.path.join(SCRIPT_DIR, '..') 
URL1 = os.path.join(AUDIT_DIR, 'CarDekho_UX_Audit_-_Heuristic_Evaluation.csv')
URL2 = os.path.join(AUDIT_DIR, 'BikeDekho_UX_Audit_-_Heuristic_Evaluation.csv')

def upload_to_catbox(filepath):
    print(f"Uploading {os.path.basename(filepath)}...")
    cmd = ["curl", "-s", "-F", "reqtype=fileupload", "-F", f"fileToUpload=@{filepath}", "https://catbox.moe/user/api.php"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.startswith("http"):
        return result.stdout.strip()
    return ""

def main():
    if not os.path.isdir(SCREENSHOT_DIR):
        print(f"⚠️  Screenshots folder not found at: {SCREENSHOT_DIR}")
        print("    Create it and place your PNG screenshots there first.")
        return

    print("Fixing CarDekho Images...")
    if not os.path.exists(URL1):
        print(f"❌  CSV not found: {URL1} — skipping CarDekho.")
    else:
        df_car = pd.read_csv(URL1)
        images = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.endswith('.png')])
        for idx, row in df_car.iterrows():
            if idx < len(images):
                img_path = os.path.join(SCREENSHOT_DIR, images[idx])
                catbox_url = upload_to_catbox(img_path)
                df_car.at[idx, 'Screenshot'] = f'=IMAGE("{catbox_url}")' if catbox_url else ""
            else:
                df_car.at[idx, 'Screenshot'] = ""
        df_car.to_csv(URL1, index=False)
        print("✅  CarDekho CSV updated.")

    print("Fixing BikeDekho Images (clearing placeholders)...")
    if not os.path.exists(URL2):
        print(f"❌  CSV not found: {URL2} — skipping BikeDekho.")
    else:
        df_bike = pd.read_csv(URL2)
        for idx, row in df_bike.iterrows():
            df_bike.at[idx, 'Screenshot'] = ""
        df_bike.to_csv(URL2, index=False)
        print("✅  BikeDekho CSV updated.")

    print("\n🎉 Done! CSVs are corrected.")

if __name__ == '__main__':
    main()
