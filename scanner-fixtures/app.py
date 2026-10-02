"""
INTENTIONAL SAST fixtures (Low → Critical) for scanner dogfooding.
Mounted conceptually under scanner-fixtures; do not expose in production.
"""

import hashlib
import http.client
import os
import sqlite3
import ssl
import subprocess
from flask import Flask, request, redirect

app = Flask(__name__)
SECRETS = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "db_password": "K8s-Batch1-Scanner-Only-P@ss",
}


# CRITICAL: OS command injection
@app.route("/critical/shell")
def critical_shell():
    host = request.args.get("host", "127.0.0.1")
    output = subprocess.check_output("ping -c 1 " + host, shell=True)
    return output


# CRITICAL: SQL injection
@app.route("/critical/sql")
def critical_sql():
    user_id = request.args.get("id", "1")
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = " + user_id)
    rows = cur.fetchall()
    conn.close()
    return {"rows": rows}


# CRITICAL: code injection via eval
@app.route("/critical/eval", methods=["POST"])
def critical_eval():
    expr = request.json.get("expr", "1+1") if request.is_json else "1+1"
    return {"result": eval(expr)}


# HIGH: path traversal
@app.route("/high/read")
def high_read():
    name = request.args.get("name", "readme.txt")
    with open(os.path.join("data", name), "r") as f:
        return f.read()


# HIGH: weak hashing
@app.route("/high/hash", methods=["POST"])
def high_hash():
    password = (request.json or {}).get("password", "password")
    return {"algorithm": "md5", "hash": hashlib.md5(password.encode()).hexdigest()}


# HIGH: SSRF
@app.route("/high/fetch")
def high_fetch():
    import urllib.request

    target = request.args.get("url", "http://127.0.0.1:8080/")
    with urllib.request.urlopen(target) as resp:
        return resp.read(500)


# HIGH: hardcoded secrets exposure
@app.route("/high/creds")
def high_creds():
    return SECRETS


# MEDIUM: reflected XSS
@app.route("/medium/xss")
def medium_xss():
    name = request.args.get("name", "guest")
    return f"<html><body><h1>Hello {name}</h1></body></html>"


# MEDIUM: open redirect
@app.route("/medium/redirect")
def medium_redirect():
    return redirect(request.args.get("next", "/"))


# MEDIUM: insecure cookie flags
@app.route("/medium/cookie")
def medium_cookie():
    resp = app.response_class(response='{"ok":true}', mimetype="application/json")
    resp.set_cookie("sessionToken", "scanner-fixture", path="/")
    return resp


# LOW: stack disclosure
@app.route("/low/error")
def low_error():
    try:
        raise RuntimeError("scanner fixture failure")
    except Exception as err:
        return str(err.__traceback__), 500


# LOW: TLS verify disabled
@app.route("/low/tls")
def low_tls():
    ctx = ssl._create_unverified_context()
    conn = http.client.HTTPSConnection("example.com", context=ctx)
    conn.request("GET", "/")
    resp = conn.getresponse()
    return {"status": resp.status, "verify": False}


# LOW: cleartext HTTP
@app.route("/low/cleartext")
def low_cleartext():
    conn = http.client.HTTPConnection("example.com")
    conn.request("GET", "/token")
    resp = conn.getresponse()
    return {"protocol": "http", "status": resp.status}


# LOW: weak PRNG
@app.route("/low/token")
def low_token():
    import random

    return {"token": hex(random.getrandbits(32)), "prng": "random"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=True)
