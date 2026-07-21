from flask import Flask, request, render_template, jsonify, redirect, url_for, abort
import os
import time
import hmac
import threading
import sqlite3
import requests
from lxml import etree
import json
import logging
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename
from ipaddress import ip_address
from collections import OrderedDict
import uuid
from pathlib import Path

# Example hardcoded AWS credentials (sensitive data leakage)
aws_access_key_id = 'AKIA2JAPX77RGLB664VE'
aws_secret = 'v5xpjkWYoy45fGKFSMajSn+sqs22WI2niacX9yO5'

app = Flask(__name__)

# In-memory bounded rate limit structures
app._cmd_rate = OrderedDict()
app._cmd_rate_lock = threading.Lock()
app._auth_attempts = OrderedDict()
app._auth_attempts_lock = threading.Lock()
app._upload_rate = OrderedDict()
app._upload_rate_lock = threading.Lock()
CMD_RATE_MAX_IPS = 10000
CMD_RATE_WINDOW = 60
CMD_RATE_MAX_REQS = 5
# Auth attempt limits
AUTH_RATE_WINDOW = 60
AUTH_RATE_MAX_REQS = 10
# Upload limits
UPLOAD_RATE_WINDOW = 3600
UPLOAD_RATE_MAX_REQS = 10

# Upload configuration
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.png', '.jpg', '.jpeg'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

# ProxyFix intentionally disabled in-application.
# If the app is deployed behind a trusted reverse proxy, enable ProxyFix at the deployment
# or WSGI configuration level and ensure the network only allows the proxy to reach this service.
# Do not enable ProxyFix here to avoid trusting X-Forwarded-* for authorization decisions.

# Allow remote admin conversations if explicitly enabled (unsafe)
ALLOW_REMOTE_ADMIN = os.environ.get('ALLOW_REMOTE_ADMIN', 'false').lower() in ('1','true')

# Get the script name from environment variable or default to empty string
SCRIPT_NAME = os.environ.get('SCRIPT_NAME', '')

# Determine if we're running locally
IS_LOCAL = os.environ.get('FLASK_ENV') == 'development'

# Set up paths relative to the app directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'data', 'tutorial.db')
UPLOADS_DIR = os.path.join(APP_DIR, 'data', 'uploads')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')

def init_db():
    # Create data and uploads directories if they don't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    
    # Create database and tables if they don't exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL
    )
    ''')
    
    # Insert some sample data if the table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin123')")
        cursor.execute("INSERT INTO users (username, password) VALUES ('user1', 'password123')")
    
    conn.commit()
    conn.close()

# Initialize database when the app starts
init_db()

# Helper: bounded per-IP rate-limit update with bounded cleanup and LRU eviction
def _rate_limit_check_and_add(bucket, lock, ip, window, max_reqs, max_ips, now, cleanup_limit=100):
    """Return (is_rate_limited, is_cap_reached)."""
    with lock:
        # prune this IP's timestamps
        recent = [t for t in bucket.get(ip, []) if now - t < window]
        if not recent:
            bucket.pop(ip, None)
        # bounded cleanup of stale buckets
        for k in list(bucket.keys())[:cleanup_limit]:
            k_recent = [t for t in bucket.get(k, []) if now - t < window]
            if not k_recent:
                bucket.pop(k, None)
            else:
                bucket[k] = k_recent
        # if map is full, evict the least-recently-used bucket to make space
        if ip not in bucket and len(bucket) >= max_ips:
            oldest_key = None
            oldest_time = now
            for k, times in bucket.items():
                last = max(times) if times else 0
                if last < oldest_time:
                    oldest_time = last
                    oldest_key = k
            if oldest_key:
                bucket.pop(oldest_key, None)
            else:
                # fallback: evict an arbitrary key
                try:
                    bucket.pop(next(iter(bucket)), None)
                except StopIteration:
                    pass
        # recompute recent and enforce per-IP rate limit
        recent = [t for t in bucket.get(ip, []) if now - t < window]
        if len(recent) >= max_reqs:
            bucket[ip] = recent
            return True, False
        recent.append(now)
        bucket[ip] = recent
        return False, False

def get_form_action():
    if IS_LOCAL:
        return "/app/app/result"
    return f"{SCRIPT_NAME}/result"

@app.route('/')
def app_route():
    return render_template('index.html', script_name=SCRIPT_NAME, form_action=get_form_action())

@app.route('/result', methods=['POST'])
def result():
    output = ''
    # 1 - SQL Injection
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    username = ''
    password = ''
    try:
        cursor.execute("SELECT * FROM users WHERE username = '%s' AND password = '%s'" % (username, password))
    except:
        pass

    # 2 - Command Execution (allowlist)
    if 'command' in request.form:
        # Determine client IP early
        def _client_ip():
            ip = request.remote_addr
            if not ip:
                abort(400)
            return ip

        ip = _client_ip()
        now = time.time()

        # Loopback-based admin restriction removed; rely on ADMIN_TOKEN and network controls.
        # Pre-auth rate limiting: throttle admin token guesses (bounded)
        is_limited, is_capped = _rate_limit_check_and_add(
            app._auth_attempts, app._auth_attempts_lock, ip,
            AUTH_RATE_WINDOW, AUTH_RATE_MAX_REQS, CMD_RATE_MAX_IPS, now
        )
        if is_capped:
            abort(429)
        if is_limited:
            abort(429)

        admin_token = request.form.get('admin_token') or request.headers.get('X-ADMIN-TOKEN') or ''
        if not ADMIN_TOKEN or not hmac.compare_digest(admin_token, ADMIN_TOKEN):
            abort(403)

        # Command execution rate limiting (protected by a lock)
        rate_limited = False
        with app._cmd_rate_lock:
            # prune timestamps for this IP
            recent = [t for t in app._cmd_rate.get(ip, []) if now - t < CMD_RATE_WINDOW]
            # evict this IP's bucket if empty
            if not recent:
                app._cmd_rate.pop(ip, None)
            # cleanup a small number of stale buckets to avoid slot exhaustion
            cleanup_limit = 100
            for k in list(app._cmd_rate.keys())[:cleanup_limit]:
                k_recent = [t for t in app._cmd_rate.get(k, []) if now - t < CMD_RATE_WINDOW]
                if not k_recent:
                    app._cmd_rate.pop(k, None)
            # enforce a cap on distinct tracked IPs to avoid unbounded memory growth
            if ip not in app._cmd_rate and len(app._cmd_rate) >= CMD_RATE_MAX_IPS:
                abort(429)
            # recompute recent after possible eviction
            recent = [t for t in app._cmd_rate.get(ip, []) if now - t < CMD_RATE_WINDOW]
            if len(recent) >= CMD_RATE_MAX_REQS:
                app._cmd_rate[ip] = recent
                rate_limited = True
            else:
                recent.append(now)
                app._cmd_rate[ip] = recent

        if rate_limited:
            output = 'Too many requests. Try again later.'
        else:
            cmd_key = request.form['command'].strip()

            try:
                # Implement each allowed operation in Python (no subprocess, no shell)
                if cmd_key == 'list_uploads':
                    try:
                        files = [f for f in os.listdir(UPLOADS_DIR) if os.path.isfile(os.path.join(UPLOADS_DIR, f))]
                        output = f"Uploads: {len(files)} file(s)" if files else "No files."
                    except Exception:
                        logging.exception('Failed to list uploads')
                        output = 'Error listing uploads.'

                elif cmd_key == 'whoami':
                    logging.info('whoami request denied by policy')
                    output = 'Operation not permitted.'

                elif cmd_key == 'date':
                    from datetime import datetime
                    output = datetime.utcnow().isoformat() + 'Z'

                elif cmd_key == 'uptime':
                    logging.info('uptime request denied by policy')
                    output = 'Operation not permitted.'

                else:
                    output = 'Requested command is not allowed.'
            except Exception:
                logging.exception('Command handling failed')
                output = 'Error: command handling failed.'

    # 3 - File Upload with no restrictions, and path traversal
    elif 'file' in request.files:
        # Require ADMIN_TOKEN to protect upload persistence
        admin_token = request.form.get('admin_token') or request.headers.get('X-ADMIN-TOKEN') or ''
        ip = request.remote_addr
        if not ip:
            abort(400)
        now = time.time()

        # Loopback-based admin restriction removed; rely on ADMIN_TOKEN and network controls.

        # Pre-auth rate limiting for uploads (bounded)
        is_limited, is_capped = _rate_limit_check_and_add(
            app._auth_attempts, app._auth_attempts_lock, ip,
            AUTH_RATE_WINDOW, AUTH_RATE_MAX_REQS, CMD_RATE_MAX_IPS, now
        )
        if is_capped:
            abort(429)
        if is_limited:
            abort(429)

        if not ADMIN_TOKEN or not hmac.compare_digest(admin_token, ADMIN_TOKEN):
            abort(403)

        # Per-IP upload rate limiting (bounded)
        is_limited, is_capped = _rate_limit_check_and_add(
            app._upload_rate, app._upload_rate_lock, ip,
            UPLOAD_RATE_WINDOW, UPLOAD_RATE_MAX_REQS, CMD_RATE_MAX_IPS, now
        )
        if is_capped:
            abort(429)
        if is_limited:
            abort(429)

        uploaded_file = request.files['file']
        orig_name = secure_filename(uploaded_file.filename)
        if not orig_name:
            output = 'Invalid filename.'
        else:
            ext = Path(orig_name).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                output = 'File type not allowed.'
            else:
                unique_name = f"{uuid.uuid4().hex}{ext}"
                save_path = os.path.join(UPLOADS_DIR, unique_name)
                uploaded_file.save(save_path)
                output = f"File uploaded successfully as {unique_name}"

    # 4 - SQL Injection via input
    elif 'sql' in request.form:
        sql = request.form['sql']
        try:
            # Execute the user's SQL query
            cursor.execute(sql)
            # Fetch all rows from the query result
            rows = cursor.fetchall()
            # Format the results for display
            if rows:
                output = "Results:\n" + "\n".join(str(row) for row in rows)
            else:
                output = "Query executed successfully, but no results found."
        except Exception as e:
            output = f"SQL Error: {e}"

    # 5 - Cross-Site Scripting (XSS)
    elif 'xss' in request.form:
        xss_input = request.form['xss']
        output = f"Reflected XSS result: {xss_input}"

    # 6 - XML External Entity (XXE) Injection
    elif 'xml' in request.form:
        xml_data = request.form['xml']
        try:
            # Use lxml to parse the XML data
            parser = etree.XMLParser(load_dtd=True, resolve_entities=True)
            tree = etree.fromstring(xml_data.encode(), parser)
            output = f"Parsed XML: {etree.tostring(tree, encoding='unicode')}"
        except Exception as e:
            output = f"XML Parsing Error: {e}"

    # 7 - Server-Side Request Forgery (SSRF)
    elif 'url' in request.form:
        url = request.form['url']
        try:
            # Get headers and data from form if provided
            headers = {}
            if 'headers' in request.form:
                headers = json.loads(request.form['headers'])
            
            data = None
            if 'data' in request.form:
                data = request.form['data']
            
            # Use POST method and handle data
            response = requests.post(url, headers=headers, data=data, verify=False)
            output = f"SSRF Response: {response.text[:200]}"
        except Exception as e:
            output = f"SSRF Error: {e}"

    # 8 - SQL injection with parameter instead of whole query
    elif 'username' in request.form:
        username = request.form['username']
        try:
            # Using parameterized query to prevent SQL injection
            query = "SELECT password FROM users WHERE username = ?"
            cursor.execute(query, (username,))
            result = cursor.fetchone()
            if result:
                output = f"Password for {username}: {result[0]}"
            else:
                output = "User not found."
        except Exception as e:
            output = f"SQL Error: {e}"

    return render_template('result.html', output=output, script_name=SCRIPT_NAME)

# Mount the Flask app under /app
application = DispatcherMiddleware(Flask('dummy_app'), {
    '/app': app
})

if __name__ == '__main__':
    # Do not auto-enable development mode or bind to all interfaces.
    if not ADMIN_TOKEN:
        print("WARNING: ADMIN_TOKEN is not set; command execution is disabled.")
    debug = IS_LOCAL
    run_simple('127.0.0.1', 8080, application, use_reloader=debug, use_debugger=False)

