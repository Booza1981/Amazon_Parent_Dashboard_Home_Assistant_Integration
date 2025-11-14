"""
Flask Web Server for Cookie Management

Provides a web interface for:
- Viewing cookie expiry status
- Auto-refreshing session (if cookies still valid)
- Uploading new cookies.json file
- Manual cookie refresh trigger
"""

import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

# Import the extractor for status checking
import sys
sys.path.insert(0, str(Path(__file__).parent))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size

COOKIES_FILE = Path(__file__).parent / "amazon_parental" / "cookies.json"

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Amazon Cookie Manager</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 24px;
            margin-bottom: 8px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 30px;
        }
        .status-card {
            background: #f7fafc;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid {{ status_color }};
        }
        .status-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        .status-icon {
            font-size: 32px;
        }
        .status-text {
            flex: 1;
            margin-left: 15px;
        }
        .status-text h2 {
            font-size: 18px;
            color: #2d3748;
            margin-bottom: 5px;
        }
        .status-text p {
            color: #718096;
            font-size: 14px;
        }
        .cookie-details {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
        }
        .cookie-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            font-size: 13px;
        }
        .cookie-name {
            color: #4a5568;
            font-weight: 500;
        }
        .cookie-expiry {
            color: #718096;
        }
        .cookie-expiry.expired {
            color: #e53e3e;
            font-weight: 600;
        }
        .cookie-expiry.warning {
            color: #ed8936;
            font-weight: 600;
        }
        .actions {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .btn {
            padding: 14px 20px;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            text-align: center;
            display: block;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
        }
        .btn-secondary {
            background: #48bb78;
            color: white;
        }
        .btn-secondary:hover {
            background: #38a169;
        }
        .btn-upload {
            background: #ed8936;
            color: white;
            position: relative;
            overflow: hidden;
        }
        .btn-upload:hover {
            background: #dd6b20;
        }
        .btn-upload input[type="file"] {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
        }
        .info-box {
            background: #edf2f7;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            font-size: 13px;
            color: #4a5568;
            line-height: 1.6;
        }
        .info-box strong {
            color: #2d3748;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #718096;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #e2e8f0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍪 Amazon Cookie Manager</h1>
            <p>Manage authentication for Amazon Parental Dashboard</p>
        </div>
        
        <div class="content">
            <div class="status-card">
                <div class="status-header">
                    <span class="status-icon">{{ status_icon }}</span>
                    <div class="status-text">
                        <h2>{{ status_title }}</h2>
                        <p>{{ status_message }}</p>
                    </div>
                </div>
                
                {% if cookie_details %}
                <div class="cookie-details">
                    <div style="font-size: 12px; color: #a0aec0; margin-bottom: 10px; text-transform: uppercase; font-weight: 600;">Cookie Expiry Status</div>
                    {% for cookie_name, cookie_info in cookie_details.items() %}
                    <div class="cookie-item">
                        <span class="cookie-name">{{ cookie_name }}</span>
                        <span class="cookie-expiry {{ cookie_info.class }}">{{ cookie_info.display }}</span>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            
            <div class="actions">
                {% if can_auto_refresh %}
                <form action="/auto-refresh" method="post" onsubmit="showLoading()">
                    <button type="submit" class="btn btn-secondary">🔄 Auto-Refresh Session</button>
                </form>
                {% endif %}
                
                <label class="btn btn-upload">
                    📤 Upload cookies.json
                    <input type="file" id="cookieFile" accept=".json" onchange="uploadFile(this)">
                </label>
                
                <a href="/status" class="btn btn-primary">🔍 Refresh Status</a>
            </div>
            
            <div class="info-box">
                <strong>How to refresh cookies manually:</strong><br>
                1. On your local machine, run: <code>python amazon_parental/refresh_cookies.py</code><br>
                2. Log in to Amazon when the browser opens<br>
                3. Upload the generated <code>cookies.json</code> file above<br>
                <br>
                <strong>Auto-refresh:</strong> Only works if cookies are still valid but expiring soon.
            </div>
        </div>
    </div>
    
    <script>
        function uploadFile(input) {
            if (input.files && input.files[0]) {
                const formData = new FormData();
                formData.append('file', input.files[0]);
                
                showLoading();
                
                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ Cookies uploaded successfully!');
                        window.location.reload();
                    } else {
                        alert('❌ Upload failed: ' + data.error);
                        window.location.reload();
                    }
                })
                .catch(error => {
                    alert('❌ Upload error: ' + error);
                    window.location.reload();
                });
            }
        }
        
        function showLoading() {
            const content = document.querySelector('.content');
            content.innerHTML = '<div class="loading"><div class="spinner"></div><br>Processing...</div>';
        }
    </script>
</body>
</html>
"""


def get_cookie_status():
    """Get current cookie status."""
    try:
        if not COOKIES_FILE.exists():
            return {
                "status": "missing",
                "status_icon": "❌",
                "status_color": "#e53e3e",
                "status_title": "Cookies Not Found",
                "status_message": "No cookies.json file found. Please upload one.",
                "cookie_details": None,
                "can_auto_refresh": False
            }
        
        # Load and check cookies
        with open(COOKIES_FILE, 'r') as f:
            cookies_data = json.load(f)
        
        cookies = cookies_data.get('cookies', [])
        critical_cookies = ['ft-session', 'ft-panda-csrf-token', 'at-acbuk']
        now = datetime.now().timestamp()
        four_hours = 4 * 60 * 60
        
        expired = False
        expiring_soon = False
        cookie_details = {}
        
        for cookie in cookies:
            if cookie['name'] in critical_cookies:
                expires = cookie.get('expires', 0)
                time_left = expires - now
                
                if expires:
                    expires_dt = datetime.fromtimestamp(expires)
                    
                    if time_left < 0:
                        expired = True
                        cookie_class = "expired"
                        display = "Expired!"
                    elif time_left < four_hours:
                        expiring_soon = True
                        cookie_class = "warning"
                        hours = int(time_left / 3600)
                        mins = int((time_left % 3600) / 60)
                        display = f"Expires in {hours}h {mins}m"
                    else:
                        cookie_class = ""
                        display = expires_dt.strftime("%Y-%m-%d %H:%M")
                    
                    cookie_details[cookie['name']] = {
                        "display": display,
                        "class": cookie_class
                    }
        
        # Determine overall status
        if expired:
            return {
                "status": "expired",
                "status_icon": "❌",
                "status_color": "#e53e3e",
                "status_title": "Cookies Expired",
                "status_message": "Authentication has expired. Please upload new cookies.",
                "cookie_details": cookie_details,
                "can_auto_refresh": False
            }
        elif expiring_soon:
            return {
                "status": "expiring",
                "status_icon": "⚠️",
                "status_color": "#ed8936",
                "status_title": "Cookies Expiring Soon",
                "status_message": "Cookies will expire soon. Use auto-refresh or upload new cookies.",
                "cookie_details": cookie_details,
                "can_auto_refresh": True
            }
        else:
            return {
                "status": "ok",
                "status_icon": "✅",
                "status_color": "#48bb78",
                "status_title": "Cookies Valid",
                "status_message": "Authentication is working correctly.",
                "cookie_details": cookie_details,
                "can_auto_refresh": True
            }
            
    except Exception as e:
        return {
            "status": "error",
            "status_icon": "⚠️",
            "status_color": "#ed8936",
            "status_title": "Status Check Error",
            "status_message": f"Could not check status: {str(e)}",
            "cookie_details": None,
            "can_auto_refresh": False
        }


@app.route('/')
@app.route('/status')
def index():
    """Show cookie status page."""
    status = get_cookie_status()
    return render_template_string(HTML_TEMPLATE, **status)


@app.route('/upload', methods=['POST'])
def upload_cookies():
    """Handle cookies.json upload."""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"})
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"})
        
        if not file.filename.endswith('.json'):
            return jsonify({"success": False, "error": "File must be a .json file"})
        
        # Read and validate JSON
        content = file.read()
        try:
            cookies_data = json.loads(content)
            # Validate structure
            if 'cookies' not in cookies_data:
                return jsonify({"success": False, "error": "Invalid cookies.json format"})
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Invalid JSON file"})
        
        # Save to cookies file
        with open(COOKIES_FILE, 'wb') as f:
            f.write(content)
        
        # Create a reload trigger file to signal the main process to reload the extractor
        reload_trigger = Path(__file__).parent / ".cookies_reloaded"
        reload_trigger.write_text(str(datetime.now().timestamp()))
        
        print(f"✅ New cookies uploaded via web UI at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return jsonify({"success": True, "message": "Cookies uploaded successfully"})
        
    except Exception as e:
        print(f"❌ Error uploading cookies: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route('/auto-refresh', methods=['POST'])
def auto_refresh():
    """Trigger auto-refresh of session."""
    try:
        # We'll trigger this via a signal file that the main process can check
        refresh_trigger = Path(__file__).parent / ".refresh_trigger"
        refresh_trigger.write_text(str(datetime.now().timestamp()))
        
        print(f"🔄 Auto-refresh triggered via web UI at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Wait a moment for refresh to happen
        import time
        time.sleep(3)
        
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"❌ Error triggering auto-refresh: {e}")
        return redirect(url_for('index'))


@app.route('/api/status')
def api_status():
    """JSON API endpoint for status."""
    return jsonify(get_cookie_status())


def run_server(host='0.0.0.0', port=5000):
    """Run the Flask server."""
    print(f"\n🌐 Cookie Manager Web UI starting on http://{host}:{port}")
    print(f"   Access from your network at http://YOUR_IP:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
