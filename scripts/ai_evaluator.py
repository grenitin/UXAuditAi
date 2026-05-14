import os
import csv
import json
import time
import uuid
import requests
import subprocess
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import base64
import litellm
from playwright.sync_api import sync_playwright
import multiprocessing

# Global status tracking for SSE
TASKS_DIR = os.path.join(os.path.dirname(__file__), '..', '.tasks')
os.makedirs(TASKS_DIR, exist_ok=True)

REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

task_status = {}

def update_status(task_id, message, complete=False, error=None, current_task=None, progress=0, visual_update=False):
    status_data = {
        "status": message,
        "complete": complete,
        "error": error,
        "current_task": current_task,
        "progress": progress,
        "visual_update": visual_update,
        "timestamp": time.time()
    }
    task_status[task_id] = status_data
    
    # Write to file for persistence and SSE consumption in app.py
    try:
        filepath = os.path.join(TASKS_DIR, f"{task_id}.json")
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w') as f:
            json.dump(status_data, f)
        os.replace(temp_filepath, filepath) # Atomic move to prevent partial reads in app.py
    except Exception as e:
        print(f"Error writing status file: {e}")

def encode_image(image_path):
    """Encodes a local image to base64 for vision models."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def focus_browser():
    """Brings the user's browser back to focus on macOS."""
    if os.name != 'posix': return # Mac only logic
    
    # Try to detect which browser is likely being used for the UI
    browsers = ["Google Chrome", "Arc", "Safari", "Microsoft Edge"]
    
    script = ""
    for browser in browsers:
        script += f'if application "{browser}" is running then tell application "{browser}" to activate\n'
    
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception as e:
        print(f"Focus error: {e}")

def get_classified_pages(base_url, max_total_links=10):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0'}
        response = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        domain = urlparse(base_url).netloc
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = href
            if not href.startswith('http'):
                full_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
            
            if urlparse(full_url).netloc == domain:
                links.append(full_url)
        
        # Simple unique list
        unique_links = list(set(links))[:max_total_links]
        return unique_links
    except Exception as e:
        print(f"Crawler error: {e}")
        return [base_url]

def run_ux_audit_worker(task_id, url, user_api_key=None, provider='gemini'):
    # Ensure directory structure exists
    STATIC_SCREENSHOTS = os.path.join(os.path.dirname(__file__), '..', 'static', 'screenshots')
    os.makedirs(STATIC_SCREENSHOTS, exist_ok=True)
    
    AUDIT_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'UX Audit')
    os.makedirs(AUDIT_FOLDER, exist_ok=True)


    try:
        update_status(task_id, "Initializing AI Handshake...", current_task="handshake")
        
        parsed_url = urlparse(url if url.startswith('http') else 'https://' + url)
        domain = parsed_url.netloc
        brand = domain.replace('www.', '').split('.')[0].capitalize()
        
        # 1. Setup AI Provider with LiteLLM
        api_key = user_api_key
        
        # Public-Ready Robust Model Selection
        model_candidates = {
            'gemini': [
                'gemini/gemini-1.5-flash',
                'gemini/gemini-flash-latest',
                'gemini/gemini-1.5-flash-latest',
                'gemini/gemini-2.0-flash'
            ],
            'openai': ['gpt-4o', 'gpt-4o-mini'],
            'anthropic': ['claude-3-5-sonnet-20240620', 'claude-3-5-sonnet-latest']
        }
        
        selected_candidates = model_candidates.get(provider, ['gemini/gemini-1.5-flash'])
        working_model_name = None
        
        # Pre-flight handshake - Try candidates until one works
        for model_name in selected_candidates:
            try:
                print(f"[Handshake Diagnostic] Verifying {model_name} for {provider}...")
                litellm.completion(
                    model=model_name,
                    messages=[{"role": "user", "content": "hi"}],
                    api_key=api_key,
                    max_tokens=1
                )
                working_model_name = model_name
                print(f"Handshake successful: {working_model_name}")
                break
            except Exception as e:
                print(f"[Handshake Diagnostic] {model_name} failed: {e}")
                continue
        
        if not working_model_name:
            raise Exception(f"AI Handshake Failed: No compatible models found for your {provider} API key. Please check your key permissions.")

        # PILOT FOCUS: Exclusively audit the landing page provided
        urls_to_crawl = [url if url.startswith('http') else 'https://' + url]

        
        headers = ["Index","Heuristic","Screenshot","Page URL","Page Name","Issue Description","Behavioral Insight","Attitudinal Insight","Cognitive Load","Severity","Priority","Recommendation", "Model", "Tokens", "Cost (Rs)"]
        audit_results = []
        
        # 2. DISCOVERY PHASE — Capturing Multi-Fold Visual Context
        screenshots_data = []
        with sync_playwright() as p:
            is_render = os.environ.get('RENDER')
            args = ["--disable-blink-features=AutomationControlled"]
            if is_render:
                args.extend(["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"])
            else:
                # Use a professional desktop resolution and remove forced positioning
                args.extend(["--window-size=1920,1080"])

            browser = p.chromium.launch(
                headless=bool(is_render),
                slow_mo=200 if not is_render else 0,
                args=args
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            for page_url in urls_to_crawl:
                try:
                    page = context.new_page()
                    print(f"Auditing: {page_url}")
                    
                    # Full DOM rendering requested ("run the dom")
                    page.goto(page_url, wait_until="networkidle", timeout=60000)
                    
                    # --- MODAL TERMINATOR ---
                    try:
                        print("Terminating potential modals/pop-ups...")
                        # 1. Try Escape key
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                        
                        # 2. Search for common 'Close' buttons (X, Close, Accept, etc.)
                        # We use a broad selector to catch common modal close buttons
                        close_selectors = [
                            "button[aria-label*='Close']", "button[aria-label*='close']",
                            ".modal-close", ".close-modal", "#close-modal",
                            ".popup-close", "[class*='close-button']", 
                            "button:has-text('Close')", "button:has-text('Accept All')",
                            ".cookie-banner-close", "#onetrust-accept-btn-handler"
                        ]
                        for selector in close_selectors:
                            try:
                                if page.locator(selector).is_visible():
                                    page.locator(selector).first.click()
                                    page.wait_for_timeout(500)
                            except: continue
                    except Exception as me:
                        print(f"Modal terminator skipped: {me}")
                    # ------------------------

                    try:
                        page.wait_for_selector('body', timeout=10000)
                    except:
                        pass

                    # Scroll logic
                    page.evaluate('''async () => {
                        await new Promise((resolve) => {
                            var totalHeight = 0;
                            var distance = 150;
                            var timer = setInterval(() => {
                                var scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if(totalHeight >= scrollHeight || totalHeight > 10000) {
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }''')

                    sections = [
                        {"name": "Above the Fold", "scroll": 0},
                        {"name": "Mid-Page Content", "scroll": 0.5},
                        {"name": "Footer & Conversion", "scroll": 1.0}
                    ]
                    
                    for section in sections:
                        section_name = section["name"]
                        scroll_pct = section["scroll"]
                        
                        page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {scroll_pct})')
                        page.wait_for_timeout(1000)
                        
                        img_filename = f"{section_name.lower().replace(' ', '_')}_{str(uuid.uuid4())[:8]}.png"
                        img_path = os.path.join(STATIC_SCREENSHOTS, img_filename)
                        page.screenshot(path=img_path, full_page=True) 
                        
                        # Relative URL for web consumption
                        cat_url = f"/static/screenshots/{img_filename}"

                        screenshots_data.append({
                            "url": page_url,
                            "section": section_name,
                            "img_path": img_path,
                            "cat_url": cat_url,
                            "data": open(img_path, "rb").read()
                        })
                        
                        # Update Live Vision
                        try:
                            static_live_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'live_audit.png')
                            import shutil
                            shutil.copy(img_path, static_live_path)
                            update_status(task_id, f"Capturing Vision: {section_name}...", current_task="discovery", visual_update=True)
                        except: pass
                    
                    page.close()
                except Exception as e:
                    print(f"Page capture error: {e}")
            
            browser.close()
            
            # 2.5 Focus restoration
            focus_browser()

        # 3. INTELLIGENCE PHASE
        if screenshots_data:
            update_status(task_id, "Synthesizing visual context...", current_task="synthesis")
            time.sleep(1) # Small delay for UI smoothness
            
            update_status(task_id, "Running UX Intelligence Analysis...", current_task="intelligence")
            
            # Prepare LiteLLM Vision Messages
            message_content = [
                {
                    "type": "text", 
                    "text": """
                    You are a Senior UX Researcher. Analyze the provided screenshots of a website and perform a detailed Heuristic Evaluation                    For each usability issue you find, provide the following details in a JSON array of objects:
                    - Heuristic: One of the 10 Nielsen Heuristics (e.g., "Visibility of System Status", "User Control and Freedom", etc.)
                    - Issue Description: A clear, concise description of the problem.
                    - Behavioral Insight: What the user might do or feel.
                    - Attitudinal Insight: What this says about the brand or product.
                    - Cognitive Load: "Low", "Medium", or "High".
                    - Severity: 1 to 5 (5 is critical).
                    - Priority: "P0", "P1", "P2", "P3".
                    - Recommendation: How to fix it.
                    - Page Name: Which part of the page this is.
                    - screenshot_index: The 0-based index of the screenshot this issue is located on.
                    - box_2d: [ymin, xmin, ymax, xmax] normalized coordinates (0-1000) representing the specific SECTION or SEGMENT where the issue occurs.
                    
                    IMPORTANT: Return ONLY the raw JSON array. No markdown, no triple backticks, no preamble.
                    """
                }
            ]
            
            for shot in screenshots_data:
                base64_image = encode_image(shot['img_path'])
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                })
            
            try:
                # Add PIL for cropping
                from PIL import Image

                response = litellm.completion(
                    model=working_model_name,
                    messages=[{"role": "user", "content": message_content}],
                    api_key=api_key,
                    response_format={"type": "json_object"} if provider != 'gemini' else None
                )
                
                raw_text = response.choices[0].message.content.strip()
                
                # Clean up potential markdown formatting if AI ignored instructions
                if raw_text.startswith('```json'):
                    raw_text = raw_text.split('```json')[1].split('```')[0].strip()
                elif raw_text.startswith('```'):
                    raw_text = raw_text.split('```')[1].split('```')[0].strip()
                
                ai_issues = json.loads(raw_text)
                # Handle case where AI returns an object with a list instead of a raw list
                if isinstance(ai_issues, dict) and 'issues' in ai_issues:
                    ai_issues = ai_issues['issues']
                elif isinstance(ai_issues, dict) and len(ai_issues) == 1:
                    first_key = list(ai_issues.keys())[0]
                    if isinstance(ai_issues[first_key], list):
                        ai_issues = ai_issues[first_key]
                
                audit_results = []
                for i, issue in enumerate(ai_issues):
                    # --- SECTIONAL SCREENSHOT GENERATOR ---
                    issue_screenshot_url = screenshots_data[0]['cat_url'] # Fallback
                    try:
                        box = issue.get('box_2d')
                        shot_idx = issue.get('screenshot_index', 0)
                        if box and len(box) == 4 and shot_idx < len(screenshots_data):
                            original_shot = screenshots_data[shot_idx]
                            with Image.open(original_shot['img_path']) as img:
                                width, height = img.size
                                # box: [ymin, xmin, ymax, xmax] in 0-1000
                                left = (box[1] / 1000) * width
                                top = (box[0] / 1000) * height
                                right = (box[3] / 1000) * width
                                bottom = (box[2] / 1000) * height
                                
                                # Add 10% padding for better context
                                pad_w = (right - left) * 0.1
                                pad_h = (bottom - top) * 0.1
                                left = max(0, left - pad_w)
                                top = max(0, top - pad_h)
                                right = min(width, right + pad_w)
                                bottom = min(height, bottom + pad_h)
                                
                                crop_filename = f"issue_{i+1}_{uuid.uuid4().hex[:6]}.png"
                                crop_path = os.path.join(STATIC_SCREENSHOTS, crop_filename)
                                img.crop((left, top, right, bottom)).save(crop_path)
                                issue_screenshot_url = f"/static/screenshots/{crop_filename}"
                    except Exception as crop_err:
                        print(f"Crop failed for issue {i}: {crop_err}")
                    # --------------------------------------

                    # Calculate Estimated Cost (Gemini 1.5 Flash Pricing approx)
                    prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
                    completion_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
                    total_tokens = prompt_tokens + completion_tokens
                    
                    # Pricing per 1M tokens (USD): Input $0.075, Output $0.30
                    cost_usd = ((prompt_tokens * 0.075) + (completion_tokens * 0.30)) / 1_000_000
                    cost_inr = cost_usd * 83 # Approx conversion
                    
                    audit_results.append({
                        "Index": str(i + 1),
                        "Heuristic": issue.get('Heuristic', 'UX Best Practices'),
                        "Screenshot": issue_screenshot_url, 
                        "Page URL": url,
                        "Page Name": issue.get('Page Name', 'General'),
                        "Issue Description": issue.get('Issue Description', 'N/A'),
                        "Behavioral Insight": issue.get('Behavioral Insight', 'N/A'),
                        "Attitudinal Insight": issue.get('Attitudinal Insight', 'N/A'),
                        "Cognitive Load": issue.get('Cognitive Load', 'Medium'),
                        "Severity": str(issue.get('Severity', '3')),
                        "Priority": issue.get('Priority', 'P2'),
                        "Recommendation": issue.get('Recommendation', 'N/A'),
                        "Model": working_model_name,
                        "Tokens": str(total_tokens),
                        "Cost (Rs)": f"{cost_inr:.4f}"
                    })
            except Exception as parse_err:
                print(f"AI Response Parsing Failed: {parse_err}")
                # Fallback to a single entry if parsing fails
                audit_results = [{
                    "Index": "1",
                    "Heuristic": "System Error",
                    "Screenshot": screenshots_data[0]['cat_url'],
                    "Page URL": url,
                    "Page Name": "Home",
                    "Issue Description": f"AI Analysis failed to parse: {str(parse_err)}",
                    "Recommendation": "Try running the audit again or check API logs.",
                    "Model": working_model_name,
                    "Severity": "5"
                }]

        # 4. REPORT PHASE
        update_status(task_id, "Generating final report...", current_task="report")
        
        # Save as Isolated JSON for production readiness
        report_filename = f"{task_id}.json"
        report_path = os.path.join(REPORTS_DIR, report_filename)
        
        report_data = {
            "task_id": task_id,
            "brand": brand,
            "url": url,
            "timestamp": time.time(),
            "issues": audit_results,
            "pages": 1 # For now, one page per audit
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        # Legacy CSV support (Optional)
        csv_filename = f"{brand}_UX_Audit.csv"
        csv_path = os.path.join(AUDIT_FOLDER, csv_filename)
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(audit_results)
        
        update_status(task_id, "Audit complete and verified!", complete=True, progress=100)
            
    except Exception as e:
        print(f"Audit failed: {e}")
        update_status(task_id, f"Error: {str(e)}", complete=True, error=str(e))

if __name__ == "__main__":
    # Test call
    run_ux_audit_worker("test_id", "https://www.google.com")
