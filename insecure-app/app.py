from flask import Flask, request, render_template, jsonify, redirect, url_for
import subprocess
import os
import sqlite3
import requests
from lxml import etree
import json
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

# Example hardcoded AWS credentials (sensitive data leakage)
aws_access_key_id = 'AKIA2JAPX77RGLB664VE'
aws_secret = 'v5xpjkWYoy45fGKFSMajSn+sqs22WI2niacX9yO5'

app = Flask(__name__)

# Get the script name from environment variable or default to empty string
SCRIPT_NAME = os.environ.get('SCRIPT_NAME', '')

# Determine if we're running locally
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

    # 2 - Command Injection
    if 'command' in request.form:
        cmd = request.form['command']
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            output = stdout.decode('utf-8')
        else:
            output = f"Error (Exit Code: {process.returncode}):\n{stderr.decode('utf-8')}"

    # 3 - File Upload with no restrictions, and path traversal
    elif 'file' in request.files:
        uploaded_file = request.files['file']
        uploaded_file.save(os.path.join(UPLOADS_DIR, uploaded_file.filename))
        output = f"File {uploaded_file.filename} uploaded successfully!"

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

# --- INTENTIONAL scanner fixtures batch 2 (Low → Critical) ---
BATCH2_SECRETS = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "api_token": "scanner-batch2-api-token-0002",
}

@app.route('/batch2/critical/shell')
def batch2_critical_shell():
    host = request.args.get('host', '127.0.0.1')
    return subprocess.check_output('ping -c 1 ' + host, shell=True)

@app.route('/batch2/critical/sql')
def batch2_critical_sql():
    user_id = request.args.get('id', '1')
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ' + user_id)
    rows = cursor.fetchall()
    db.close()
    return jsonify(rows)

@app.route('/batch2/critical/eval', methods=['POST'])
def batch2_critical_eval():
    expr = (request.get_json(silent=True) or {}).get('expr', '1+1')
    return jsonify({"result": eval(expr)})

@app.route('/batch2/high/read')
def batch2_high_read():
    name = request.args.get('name', 'tutorial.db')
    with open(os.path.join(APP_DIR, 'data', name), 'rb') as f:
        return f.read()

@app.route('/batch2/high/hash', methods=['POST'])
def batch2_high_hash():
    import hashlib
    password = (request.get_json(silent=True) or {}).get('password', 'password')
    return jsonify({"algorithm": "md5", "hash": hashlib.md5(password.encode()).hexdigest()})

@app.route('/batch2/high/ssrf')
def batch2_high_ssrf():
    target = request.args.get('url', 'http://127.0.0.1:8080/')
    response = requests.get(target, verify=False)
    return response.text[:500]

@app.route('/batch2/high/creds')
def batch2_high_creds():
    return jsonify(BATCH2_SECRETS)

@app.route('/batch2/medium/xss')
def batch2_medium_xss():
    name = request.args.get('name', 'guest')
    return f'<html><body><h1>Hello {name}</h1></body></html>'

@app.route('/batch2/medium/redirect')
def batch2_medium_redirect():
    return redirect(request.args.get('next', '/'))

@app.route('/batch2/low/error')
def batch2_low_error():
    try:
        raise RuntimeError('batch2 scanner fixture')
    except Exception:
        import traceback
        return traceback.format_exc(), 500

@app.route('/batch2/low/tls')
def batch2_low_tls():
    response = requests.get('https://example.com', verify=False)
    return jsonify({"status": response.status_code, "verify": False})

@app.route('/batch2/low/token')
def batch2_low_token():
    import random
    return jsonify({"token": hex(random.getrandbits(32)), "prng": "random"})

# Mount the Flask app under /app
application = DispatcherMiddleware(Flask('dummy_app'), {
    '/app': app
})

if __name__ == '__main__':
    # Set environment to development for local testing
    os.environ['FLASK_ENV'] = 'development'
    run_simple('0.0.0.0', 8080, application, use_reloader=True, use_debugger=True)

