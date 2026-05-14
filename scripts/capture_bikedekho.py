import pandas as pd
import subprocess
from playwright.sync_api import sync_playwright
import time
import os

URL2 = 'UX Audit/BikeDekho_UX_Audit_-_Heuristic_Evaluation.csv'

def upload_to_catbox(filepath):
    print(f"Uploading {os.path.basename(filepath)}...")
    cmd = ["curl", "-s", "-F", "reqtype=fileupload", "-F", f"fileToUpload=@{filepath}", "https://catbox.moe/user/api.php"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.startswith("http"):
        return result.stdout.strip()
    return ""

def main():
    df_bike = pd.read_csv(URL2)
    urls_to_capture = df_bike['Page URL'].unique()
    
    screenshot_map = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Desktop viewport for website heuristic evaluation
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        for url in urls_to_capture:
            print(f"Capturing {url}...")
            try:
                page.goto(url, timeout=30000, wait_until="load")
                time.sleep(2) # Give it an extra moment to render images/fonts
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
        
    df_bike['Screenshot'] = df_bike['Screenshot'].astype(object)
    
    for idx, row in df_bike.iterrows():
        url = row['Page URL']
        if url in screenshot_map:
            df_bike.at[idx, 'Screenshot'] = f'=IMAGE("{screenshot_map[url]}")'
            
    df_bike.to_csv(URL2, index=False)
    print("Done BikeDekho!")

if __name__ == '__main__':
    main()
