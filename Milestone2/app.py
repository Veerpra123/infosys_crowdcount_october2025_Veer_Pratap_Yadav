import os, sqlite3, json, atexit
from datetime import timedelta
from functools import wraps

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import (
    Flask, g, request, render_template, redirect, url_for,
    jsonify, make_response, abort, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies
)

# STREAM + YOLO
from services.video_stream import VideoStream
from services.detector import Detector

# ---------------- YOLO Detector ----------------
detector = Detector("yolov8n.pt", conf=0.50)
detector.load()

# -------------------- App setup --------------------
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")

app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

jwt = JWTManager(app)
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------- DB helpers --------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','viewer')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            points TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()

with app.app_context():
    init_db()

# -------------------- Auth helpers --------------------
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
    def wrapper(fn):
        @wraps(fn)
        @jwt_required(locations=["cookies"])
        def decorated(*args, **kw):
            user = current_user()
            if not user or user["role"] not in roles:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "message": "Forbidden"}), 403
                return abort(403)
            return fn(*args, **kw)
        return decorated
    return wrapper

# -------------------- JWT error handlers --------------------
@jwt.unauthorized_loader
def _unauth(_):
    if request.path.startswith("/api/"): return jsonify({"ok": False,"message":"Unauthorized"}),401
    return redirect(url_for("login_page"))

@jwt.invalid_token_loader
def _inv(_):
    if request.path.startswith("/api/"): return jsonify({"ok": False,"message":"Invalid token"}),401
    return redirect(url_for("login_page"))

@jwt.expired_token_loader
def _exp(_, __):
    if request.path.startswith("/api/"): return jsonify({"ok": False,"message":"Token expired"}),401
    return redirect(url_for("login_page"))

# -------------------- Pages --------------------
@app.get("/")
def home(): return redirect(url_for("login_page"))

@app.get("/register")
def register_page(): return render_template("register.html")

@app.get("/login")
def login_page(): return render_template("login.html")

@app.get("/admin/dashboard")
@jwt_required(locations=["cookies"])
def dashboard_page():
    u = current_user()
    if not u: return redirect(url_for("login_page"))
    return render_template("dashboard.html", user=dict(u))

# -------------------- Auth API --------------------
@app.post("/api/register")
def api_register():
    data = request.get_json() or {}
    name = data.get("name","").strip()
    email = data.get("email","").strip().lower()
    pw = data.get("password","")

    if not name or not email or not pw:
        return jsonify({"ok": False,"message":"All fields required"}),400

    db = get_db()
    role = "admin" if db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]==0 else "viewer"
    try:
        db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                   (name,email,generate_password_hash(pw),role)); db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"ok": False,"message":"Email exists"}),409

    return jsonify({"ok": True,"message":"Registered"}),201

@app.post("/api/login")
def api_login():
    data = request.get_json() or {}
    email = data.get("email",""); pw = data.get("password","")

    db = get_db()
    u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not check_password_hash(u["password_hash"],pw):
        return jsonify({"ok":False,"message":"Invalid"}),401

    token = create_access_token(identity=email)
    resp = make_response(jsonify({"ok":True,"message":"Logged in"}))
    set_access_cookies(resp,token)
    return resp

@app.post("/api/logout")
def api_logout():
    resp = make_response(jsonify({"ok":True}))
    unset_jwt_cookies(resp)
    return resp

# ---------------- STREAM CONTROL ----------------
_stream = None
_source_mode = "none"
_still_frame = None
_source_path = None

def stop_stream():
    global _stream
    if _stream:
        try: _stream.stop()
        except: pass
        _stream = None

@app.post("/api/camera/start")
@jwt_required(locations=["cookies"])
def start_cam():
    global _stream,_source_mode,_still_frame,_source_path
    stop_stream()
    _still_frame = None
    cam = os.getenv("CAMERA_INDEX","0")
    src = int(cam) if cam.isdigit() else cam
    _stream = VideoStream(src).start()
    _source_mode = "webcam"; _source_path=None
    return jsonify({"ok":True})

@app.post("/api/camera/stop")
@jwt_required(locations=["cookies"])
def stop_cam():
    global _source_mode,_still_frame,_source_path
    stop_stream()
    _still_frame=None; _source_mode="none"; _source_path=None
    return jsonify({"ok":True})

@app.post("/api/upload/video")
@jwt_required(locations=["cookies"])
def upload_video():
    global _stream,_still_frame,_source_mode,_source_path
    if "file" not in request.files: return jsonify({"ok":False}),400
    f = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".mp4",".avi",".mkv",".mov"]: return jsonify({"ok":False}),400
    path = os.path.join(UPLOAD_DIR, f"vid_{f.filename}")
    f.save(path)
    stop_stream()
    _still_frame=None; _stream = VideoStream(path).start()
    _source_mode="video"; _source_path=path
    return jsonify({"ok":True})

@app.post("/api/upload/image")
@jwt_required(locations=["cookies"])
def upload_image():
    global _stream,_still_frame,_source_mode,_source_path
    if "file" not in request.files: return jsonify({"ok":False}),400
    data = request.files["file"].read()
    arr = np.frombuffer(data,np.uint8)
    im = cv2.imdecode(arr,cv2.IMREAD_COLOR)
    if im is None: return jsonify({"ok":False}),400
    stop_stream()
    _still_frame=im; _source_mode="image"; _source_path=None
    return jsonify({"ok":True})

# ---------------- LIVE STREAM ----------------
def mjpeg_generator():
    blank = np.zeros((480,640,3),dtype=np.uint8)

    while True:
        frame=None
        if _stream:
            try: frame=_stream.read()
            except: frame=None

        if frame is None:
            frame = _still_frame.copy() if _still_frame is not None else blank.copy()
            if _still_frame is None:
                cv2.putText(frame,"No source. Start camera or upload video/image.",
                            (22,240),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),2)

        # ✅ YOLO processing
        try:
            frame = detector.process(frame)
        except:
            pass

        ok,buf=cv2.imencode(".jpg",frame)
        if not ok: continue
        yield(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+buf.tobytes()+b"\r\n")

@app.get("/video")
@jwt_required(locations=["cookies"])
def video(): 
    return Response(mjpeg_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")

@atexit.register
def cleanup(): stop_stream()

# ---------------- ZONES API ----------------
def valid_points(pts):
    return isinstance(pts,list) and len(pts)>=3

@app.get("/api/zones")
@jwt_required(locations=["cookies"])
def zones_list():
    rows = get_db().execute("SELECT * FROM zones ORDER BY id").fetchall()
    out=[{"id":r["id"],"name":r["name"],"points":json.loads(r["points"])} for r in rows]
    return jsonify(out)

@app.post("/api/zones")
@role_required("admin")
def zone_create():
    data=request.get_json() or {}
    name=data.get("name","").strip()
    pts=data.get("points",[])
    if not name or not valid_points(pts):
        return jsonify({"ok":False,"message":"Invalid zone"}),400
    get_db().execute("INSERT INTO zones(name,points) VALUES(?,?)",(name,json.dumps(pts)))
    get_db().commit()
    return jsonify({"ok":True})

@app.delete("/api/zones/<int:id>")
@role_required("admin")
def zone_delete(id):
    db=get_db()
    if not db.execute("SELECT id FROM zones WHERE id=?",(id,)).fetchone():
        return jsonify({"ok":False,"message":"Not found"}),404
    db.execute("DELETE FROM zones WHERE id=?",(id,)); db.commit()
    return jsonify({"ok":True})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
