import os
import sqlite3
from datetime import timedelta
from functools import wraps
from flask import (
    Flask, g, request, render_template, redirect, url_for,
    jsonify, make_response, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies
)
from dotenv import load_dotenv

# -------------------- App setup --------------------
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")

# Store JWT in HttpOnly cookies
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = False        # True in production (HTTPS)
app.config["JWT_COOKIE_SAMESITE"] = "Lax"      # "None" only with HTTPS
app.config["JWT_COOKIE_CSRF_PROTECT"] = False  # Consider enabling in prod
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=6)

jwt = JWTManager(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

# -------------------- DB helpers --------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','viewer')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()

# Flask 3.x friendly: init DB on startup
with app.app_context():
    init_db()

# -------------------- Auth utilities --------------------
def current_user():
    email = get_jwt_identity()
    if not email:
        return None
    db = get_db()
    return db.execute(
        "SELECT id, name, email, role FROM users WHERE email = ?",
        (email,)
    ).fetchone()

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required(locations=["cookies"])
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or user["role"] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Make JWT errors redirect to /login (nice UX)
@jwt.unauthorized_loader
def _unauth(_reason):
    return redirect(url_for("login_page"))

@jwt.invalid_token_loader
def _invalid(_reason):
    return redirect(url_for("login_page"))

@jwt.expired_token_loader
def _expired(_header, _payload):
    return redirect(url_for("login_page"))

# -------------------- Pages --------------------
@app.get("/")
def home():
    return redirect(url_for("login_page"))

@app.get("/register")
def register_page():
    return render_template("register.html")

@app.get("/login")
def login_page():
    return render_template("login.html")

@app.get("/admin/dashboard")
@jwt_required(locations=["cookies"])
def dashboard_page():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", user=dict(user))

# -------------------- API: Auth --------------------
@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"ok": False, "message": "All fields are required."}), 400

    db = get_db()
    # First ever user becomes admin
    total = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    role = "admin" if total == 0 else "viewer"

    try:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role)
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "message": "Email already registered."}), 409

    # No auto-login: user should log in next
    return jsonify({"ok": True, "message": "Registered successfully. Please log in."}), 201

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"ok": False, "message": "Email and password required."}), 400

    db = get_db()
    user = db.execute(
        "SELECT id, name, email, password_hash, role FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "message": "Invalid credentials."}), 401

    token = create_access_token(identity=email)
    resp = make_response(jsonify({"ok": True, "message": "Logged in."}))
    set_access_cookies(resp, token)
    return resp

@app.post("/api/logout")
def api_logout():
    resp = make_response(jsonify({"ok": True, "message": "Logged out."}))
    unset_jwt_cookies(resp)
    return resp

@app.get("/api/me")
@jwt_required(locations=["cookies"])
def api_me():
    user = current_user()
    if not user:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "user": dict(user)})

# -------------------- Run --------------------
if __name__ == "__main__":
    app.run(debug=True)
