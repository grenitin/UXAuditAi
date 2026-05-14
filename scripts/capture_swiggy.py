import pandas as pd
import subprocess
from playwright.sync_api import sync_playwright
import time
import os

URL_SWIGGY = 'UX Audit/Swiggy_UX_Audit_-_Heuristic_Evaluation.csv'

def upload_to_catbox(filepath):
    print(f"Uploading {os.path.basename(filepath)}...")
    cmd = ["curl", "-s", "-F", "reqtype=fileupload", "-F", f"fileToUpload=@{filepath}", "https://catbox.moe/user/api.php"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.startswith("http"):
        return result.stdout.strip()
    return ""

def main():
    df = pd.read_csv(URL_SWIGGY)
    urls_to_capture = df['Page URL'].unique()
    
    screenshot_map = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Desktop viewport constraint
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        for url in urls_to_capture:
            print(f"Capturing {url}...")
            try:
                page.goto(url, timeout=30000, wait_until="load")
                time.sleep(3) # Let all heavy food banners, icons, lazy loading finish!
                safe_name = url.replace("https://", "").replace("/", "_").replace(".", "_") + ".png"
                img_path = f"/tmp/{safe_name}"
                page.screenshot(path=img_path)
                
                # Upload to catbox
                cat_url = upload_to_catbox(img_path)
                if cat_url:
                    screenshot_map[url] = cat_url
            except Exception as e:
                print(f"Failed on {url}: {e}")
        
        browser.close()
        
    df['Screenshot'] = df['Screenshot'].astype(object)
    
    for idx, row in df.iterrows():
        url = row['Page URL']
        if url in screenshot_map:
            df.at[idx, 'Screenshot'] = f'=IMAGE("{screenshot_map[url]}")'
            
    df.to_csv(URL_SWIGGY, index=False)
    print("Done Swiggy Capture!")

if __name__ == '__main__':
    main()
