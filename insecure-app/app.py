from flask import Flask, request, render_template, jsonify, redirect, url_for, abort
import subprocess
import os
import sqlite3
import requests
from lxml import etree
import json
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename
from pathlib import Path
import uuid

# Example hardcoded AWS credentials (sensitive data leakage)
aws_access_key_id = 'AKIA2JAPX77RGLB664VE'
aws_secret = 'v5xpjkWYoy45fGKFSMajSn+sqs22WI2niacX9yO5'

app = Flask(__name__)
# Limit maximum upload size to 10 MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# Allowed upload extensions
ALLOWED_EXTS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}

# Get the script name from environment variable or default to empty string
SCRIPT_NAME = os.environ.get('SCRIPT_NAME', '')

# Determine if we're running locally (used for form action only)
IS_LOCAL = os.environ.get('FLASK_ENV') == 'development'

# Set up paths relative to the app directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'data', 'tutorial.db')
UPLOADS_DIR = os.path.join(APP_DIR, 'data', 'uploads')

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

    # 2 - Command Execution (safe whitelist, no shell)
    if 'command' in request.form:
        user_cmd = request.form['command'].strip()
        # Only allow a small set of predefined commands without arguments
        allowed_commands = {
            'date': ['date'],
            'uptime': ['uptime'],
            'whoami': ['whoami'],
            'id': ['id'],
            'hostname': ['hostname'],
        }
        if user_cmd in allowed_commands:
            try:
                process = subprocess.Popen(allowed_commands[user_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    output = stdout.decode('utf-8')
                else:
                    output = f"Error (Exit Code: {process.returncode}):\n{stderr.decode('utf-8')}"
            except Exception as e:
                output = f"Command Execution Error: {e}"
        else:
            output = "Command not allowed."

    # 3 - File Upload with filename sanitization, size limit, allowlist and safe storage
    elif 'file' in request.files:
        uploaded_file = request.files['file']
        # Sanitize the filename
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            output = "Invalid filename."
        else:
            # Require a file extension and check it against the allowlist
            if '.' not in filename:
                output = "File must have an allowed extension."
            else:
                ext = filename.rsplit('.', 1)[1].lower()
                if ext not in ALLOWED_EXTS:
                    output = "File type not allowed."
                else:
                    base_dir = Path(UPLOADS_DIR).resolve()
                    # Generate a server-side random filename to prevent overwrites
                    safe_name = f"{uuid.uuid4().hex}.{ext}"
                    dest_path = (base_dir / safe_name).resolve()
                    try:
                        dest_path.relative_to(base_dir)
                    except Exception:
                        output = "Invalid filename."
                    else:
                        uploaded_file.save(str(dest_path))
                        output = f"File uploaded successfully as {safe_name}"

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
    # Only enable the debugger and reloader when explicitly allowed via ENABLE_DEBUGGER=1
    DEBUG_MODE = os.environ.get('ENABLE_DEBUGGER') == '1'
    if DEBUG_MODE:
        # Bind debugger to localhost only to reduce accidental exposure
        run_simple('127.0.0.1', 8080, application, use_reloader=True, use_debugger=True)
    else:
        run_simple('0.0.0.0', 8080, application, use_reloader=False, use_debugger=False)
