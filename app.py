"""
UX Audit — Flask Web Server
============================
Serves the audit UI and runs ai_evaluator.py as a background task.

Usage:
    python app.py

Then open: http://localhost:5050
"""

import sys
import os

# Force Playwright to use the persistent cloud path
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(os.path.dirname(__file__), 'pw-browsers')



import uuid
import json
import threading
import multiprocessing
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Add scripts/ to path so we can import ai_evaluator directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
import ai_evaluator

app = Flask(__name__, template_folder='templates', static_folder='static')


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run_audit', methods=['POST'])
def run_audit():
    data = request.get_json()
    url  = (data or {}).get('url', '').strip()
    api_key = (data or {}).get('api_key', '').strip()
    provider = (data or {}).get('provider', 'gemini').strip()
    
    if not api_key:
        return jsonify({'error': 'API Key is required'}), 400
        
    task_id = str(uuid.uuid4())
    # multiprocessing.Process with 'spawn' is more stable than threading on macOS for vision tasks
    # as it prevents gRPC/Playwright file descriptor leakage from the parent process.
    ai_evaluator.update_status(task_id, f"Spawning isolated audit process ({provider})...")

    p = multiprocessing.Process(target=ai_evaluator.run_ux_audit_worker, args=(task_id, url, api_key, provider))
    p.start()

    return jsonify({'task_id': task_id})


@app.route('/status/<task_id>')
def status(task_id):
    """Server-Sent Events — streams live status to the browser."""
    def generate():
        import time
        import json
        last_status = None
        last_task   = None
        
        filepath = os.path.join(ai_evaluator.TASKS_DIR, f"{task_id}.json")
        
        while True:
            if not os.path.exists(filepath):
                time.sleep(0.5)
                continue
                
            try:
                with open(filepath, 'r') as f:
                    task = json.load(f)
            except Exception:
                time.sleep(0.5)
                continue

            current_msg = task.get('status')
            current_task = task.get('current_task')
            
            if (current_msg != last_status) or (current_task != last_task):
                yield f"data: {json.dumps(task)}\n\n"
                last_status = current_msg
                last_task = current_task

            if task.get('complete'):
                break

            time.sleep(1)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/results/<task_id>')
def results(task_id):
    """Return isolated audit results for a specific task."""
    report_path = os.path.join(ai_evaluator.REPORTS_DIR, f"{task_id}.json")
    
    if not os.path.exists(report_path):
        return jsonify({'error': 'Report not found', 'issues': [], 'pages': 0}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        return jsonify(report_data)
    except Exception as e:
        return jsonify({'error': str(e), 'issues': [], 'pages': 0}), 500


@app.route('/update_results/<task_id>', methods=['POST'])
def update_results(task_id):
    """Update audit results (manual overrides) for a specific task."""
    report_path = os.path.join(ai_evaluator.REPORTS_DIR, f"{task_id}.json")
    if not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404

    try:
        data = request.get_json()
        new_issues = data.get('issues')
        if new_issues is None:
            return jsonify({'error': 'No issues provided'}), 400

        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        # Update the issues in the report data
        report_data['issues'] = new_issues
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# --- SMTP CONFIGURATION ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "") 
SMTP_PASS = os.getenv("SMTP_PASS", "")


def send_invitation_email(to_email, brand_name, share_url):
    """Sends a professional HTML invitation email."""
    if "xxxx" in SMTP_PASS:
        print("[EMAIL] Skipping send: SMTP credentials not configured.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Invitation: View UX Audit Report for {brand_name}"
        msg["From"] = f"UX Audit Engine <{SMTP_USER}>"
        msg["To"] = to_email

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #0a0a0c; color: #fff; padding: 40px;">
            <div style="max-width: 600px; margin: 0 auto; background: #141419; border: 1px solid #2a2a32; border-radius: 16px; padding: 40px; text-align: center;">
                <h1 style="color: #fff; font-size: 24px;">UX Heuristic Evaluation</h1>
                <p style="color: #a1a1aa; font-size: 16px;">You have been invited to view the professional UX audit report for <strong>{brand_name}</strong>.</p>
                <div style="margin: 30px 0;">
                    <a href="{share_url}" style="background: #7c6ef2; color: #fff; padding: 12px 30px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">View Full Report</a>
                </div>
                <p style="color: #a1a1aa; font-size: 12px;">This is a secure, view-only link generated by the UX Audit Engine.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

# --- SHARED REPORT PERSISTENCE ---
SHARED_DIR = os.path.join(os.path.dirname(__file__), 'shared_reports')
os.makedirs(SHARED_DIR, exist_ok=True)

@app.route('/api/share', methods=['POST'])
def api_share():
    """Receive audit data, save it as a shared JSON, and send invite email."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid JSON data'}), 400
        
    email = data.get('email')
    audit_data = data.get('audit_data')
    brand = audit_data.get('brand', 'UX Audit') if audit_data else 'UX Audit'
    
    if not audit_data:
        return jsonify({'status': 'error', 'message': 'No audit data provided'}), 400
        
    share_id = str(uuid.uuid4())
    file_path = os.path.join(SHARED_DIR, f"{share_id}.json")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(audit_data, f, indent=2)
            
        share_url = f"{request.host_url}view/{share_id}"
        
        # --- SEND LIVE EMAIL ---
        email_sent = False
        if email:
            email_sent = send_invitation_email(email, brand, share_url)
        
        return jsonify({
            'status': 'success', 
            'share_url': share_url,
            'email_sent': email_sent
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/view/<share_id>')
def view_shared_report(share_id):
    """Public view-only route for shared reports."""
    file_path = os.path.join(SHARED_DIR, f"{share_id}.json")
    if not os.path.exists(file_path):
        return "<h1>404: Report Not Found</h1><p>The link might have expired or is incorrect.</p>", 404
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)
            
        # Robustly handle issues list
        issues_raw = audit_data.get('issues', [])
        # If issues_raw is a number (count), treat it as an empty list for viewing
        if isinstance(issues_raw, int):
            issues = []
        else:
            issues = issues_raw

        return render_template('view_report.html', issues=issues, brand=audit_data.get('brand', 'UX Audit'), share_id=share_id)
    except Exception as e:
        return f"<h1>Error loading report</h1><p>{str(e)}</p>", 500

@app.route('/report/<task_id>')
def audit_report(task_id):
    """Internal interactive report page for the auditor."""
    import ai_evaluator
    report_path = os.path.join(ai_evaluator.REPORTS_DIR, f"{task_id}.json")
    if not os.path.exists(report_path):
        return f"<h1>404: Report Not Found</h1><p>No local data for task {task_id}.</p>", 404
        
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        issues = report_data.get('issues', [])
        brand = report_data.get('brand', 'UX Audit')
        url = report_data.get('url', '')
        
        return render_template('audit_report.html', task_id=task_id, issues=issues, brand=brand, url=url)
    except Exception as e:
        return f"<h1>Error loading report</h1><p>{str(e)}</p>", 500

@app.route('/download_report/<task_id>')
def download_report(task_id):
    """Generate and serve an Excel (.xlsx) version of the audit report."""
    import pandas as pd
    import io
    report_path = os.path.join(ai_evaluator.REPORTS_DIR, f"{task_id}.json")
    if not os.path.exists(report_path):
        return "Report not found", 404
        
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        issues = report_data.get('issues', [])
        brand = report_data.get('brand', 'UX_Audit')
        
        if not issues:
            return "No data to export", 400

        # Convert to DataFrame
        df = pd.DataFrame(issues)
        
        # Select and reorder columns to match our desired format
        desired_columns = ["Index", "Heuristic", "Page Name", "Issue Description", "Behavioral Insight", "Attitudinal Insight", "Cognitive Load", "Severity", "Priority", "Recommendation", "Model", "Tokens", "Cost (Rs)"]
        # Only keep columns that actually exist in the data
        df = df[[c for c in desired_columns if c in df.columns]]
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='UX Audit Report')
            
        excel_data = output.getvalue()
        output.close()
        
        filename = f"{brand.replace(' ', '_')}_UX_Audit_{task_id[:8]}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return f"Error generating Excel: {str(e)}", 500

@app.route('/download_shared/<share_id>')
def download_shared(share_id):
    """Generate and serve an Excel (.xlsx) version of a shared report."""
    import pandas as pd
    import io
    file_path = os.path.join(SHARED_DIR, f"{share_id}.json")
    if not os.path.exists(file_path):
        return "Report not found", 404
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)
        
        issues = audit_data.get('issues', [])
        brand = audit_data.get('brand', 'UX_Audit')
        
        if not issues:
            return "No data to export", 400

        df = pd.DataFrame(issues)
        desired_columns = ["Index", "Heuristic", "Page Name", "Issue Description", "Behavioral Insight", "Attitudinal Insight", "Cognitive Load", "Severity", "Priority", "Recommendation", "Model", "Tokens", "Cost (Rs)"]
        df = df[[c for c in desired_columns if c in df.columns]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='UX Audit Report')
            
        excel_data = output.getvalue()
        output.close()
        
        filename = f"{brand.replace(' ', '_')}_UX_Audit_Shared.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return f"Error generating Excel: {str(e)}", 500

if __name__ == '__main__':
    # Ensure spawn method is used for macOS stability
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
        
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    port = int(os.getenv("FLASK_PORT", 5051))
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    print(f"\n🚀 UX Audit Server running at: http://localhost:{port}\n")
    # Disabled reloader to prevent Playwright session crashes on macOS
    app.run(host='0.0.0.0', debug=debug_mode, use_reloader=False, port=port, threaded=True)
