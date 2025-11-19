# app.py
import os, sqlite3, json, atexit, time, csv, io
from datetime import timedelta, datetime
from collections import deque
from functools import wraps

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import (
    Flask, g, request, render_template, redirect, url_for,
    jsonify, make_response, abort, Response, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies
)

from services.video_stream import VideoStream
from services.detector import Detector, unique_ids_in_zone

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
APP_DIR    = os.path.dirname(__file__)
DB_PATH    = os.path.join(APP_DIR, "app.db")
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
REPORT_DIR = os.path.join(UPLOAD_DIR, "reports")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# --------- in-memory metrics buffer for exports ----------
METRICS = deque(maxlen=6*60*6)  # ~3 hours if 1 point/sec

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

        -- simple key/value settings (global)
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- M4: camera registry
        CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rtsp_url TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- M4: system/user logs
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL,              -- INFO|WARN|ERROR
            actor_email TEXT,
            action TEXT NOT NULL,
            meta_json TEXT
        );

        -- M4: stored reports library (files we keep)
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_from INTEGER,
            ts_to INTEGER,
            kind TEXT NOT NULL,               -- csv|pdf
            path TEXT NOT NULL,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # defaults
    if not db.execute("SELECT 1 FROM settings WHERE key='alert_threshold'").fetchone():
        db.execute("INSERT INTO settings(key,value) VALUES('alert_threshold','20')")
    db.commit()

with app.app_context():
    init_db()

# -------------------- Logging helper --------------------
def log_event(level: str, action: str, meta: dict | None = None):
    """Write an event to logs table. Safe/no-throw."""
    try:
        actor = get_jwt_identity()
    except Exception:
        actor = None
    try:
        db = get_db()
        db.execute(
            "INSERT INTO logs(level,actor_email,action,meta_json) VALUES(?,?,?,?)",
            (str(level).upper(), actor, action, json.dumps(meta or {}))
        )
        db.commit()
    except Exception:
        pass

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

# -------------------- Admin Pages --------------------
# Admin pages — make endpoints match templates
@app.get("/admin/cameras", endpoint="admin_cameras_page")
@role_required("admin")
def admin_cameras_page():
    u = current_user()
    return render_template("admin_cameras.html", user=dict(u))

@app.get("/admin/logs", endpoint="admin_logs_page")
@role_required("admin")
def admin_logs_page():
    u = current_user()
    return render_template("admin_logs.html", user=dict(u))

@app.get("/admin/reports", endpoint="admin_reports_page")
@role_required("admin")
def admin_reports_page():
    u = current_user()
    return render_template("admin_reports.html", user=dict(u))

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

    log_event("INFO", "user_register", {"email": email, "role": role})
    return jsonify({"ok": True,"message":"Registered"}),201

@app.post("/api/login")
def api_login():
    data = request.get_json() or {}
    email = data.get("email",""); pw = data.get("password","")

    db = get_db()
    u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not check_password_hash(u["password_hash"],pw):
        log_event("WARN", "login_failed", {"email": email})
        return jsonify({"ok":False,"message":"Invalid"}),401

    token = create_access_token(identity=email)
    resp = make_response(jsonify({"ok":True,"message":"Logged in"}))
    set_access_cookies(resp,token)
    log_event("INFO", "login_success", {"email": email})
    return resp

@app.post("/api/logout")
def api_logout():
    resp = make_response(jsonify({"ok":True}))
    unset_jwt_cookies(resp)
    log_event("INFO", "logout", {})
    return resp

# -------------------- Current User Info (role check) --------------------
@app.get("/api/me")
@jwt_required(locations=["cookies"])
def api_me():
    u = current_user()
    if not u:
        return jsonify({"ok": False})
    return jsonify({
        "ok": True,
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "role": u["role"]
    })

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
    log_event("INFO", "camera_start", {"source": src})
    return jsonify({"ok":True})

@app.post("/api/camera/stop")
@jwt_required(locations=["cookies"])
def stop_cam():
    global _source_mode,_still_frame,_source_path
    stop_stream()
    _still_frame=None; _source_mode="none"; _source_path=None
    log_event("INFO", "camera_stop", {})
    return jsonify({"ok":True})

@app.post("/api/upload/video")
@jwt_required(locations=["cookies"])
def upload_video():
    global _stream,_still_frame,_source_mode,_source_path
    if "file" not in request.files: 
        return jsonify({"ok":False,"message":"file missing"}),400
    f = request.files["file"]
    fname = os.path.basename(f.filename)
    ext = os.path.splitext(fname)[1].lower()
    if ext not in [".mp4",".avi",".mkv",".mov"]: 
        return jsonify({"ok":False,"message":"unsupported"}),400
    path = os.path.join(UPLOAD_DIR, f"vid_%s" % fname)
    f.save(path)
    stop_stream()
    _still_frame=None; _stream = VideoStream(path).start()
    _source_mode="video"; _source_path=path
    log_event("INFO", "upload_video", {"file": fname, "path": path})
    return jsonify({"ok":True})

@app.post("/api/upload/image")
@jwt_required(locations=["cookies"])
def upload_image():
    global _stream,_still_frame,_source_mode,_source_path
    if "file" not in request.files: 
        return jsonify({"ok":False,"message":"file missing"}),400
    data = request.files["file"].read()
    arr = np.frombuffer(data,np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if im is None: 
        return jsonify({"ok":False,"message":"bad image"}),400
    stop_stream()
    _still_frame=im; _source_mode="image"; _source_path=None
    log_event("INFO", "upload_image", {"bytes": len(data)})
    return jsonify({"ok":True})

# ---------------- ZONES HELPERS ----------------
# --- add these helpers near your other utils ---
def _normalize_points(pts_raw):
    """Return list of {'x':int,'y':int} from either [{'x','y'}] or [[x,y]]."""
    out = []
    if not isinstance(pts_raw, list):
        return out
    for p in pts_raw:
        if isinstance(p, dict) and 'x' in p and 'y' in p:
            try:
                out.append({'x': int(p['x']), 'y': int(p['y'])})
            except:
                pass
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                out.append({'x': int(p[0]), 'y': int(p[1])})
            except:
                pass
    return out

def _zones_from_db():
    rows = get_db().execute("SELECT id,name,points FROM zones ORDER BY id").fetchall()
    zones = []
    for r in rows:
        try:
            raw = json.loads(r["points"])
        except:
            raw = []
        zones.append({
            "id": r["id"],
            "name": r["name"],
            "points": _normalize_points(raw)  # << always {x,y}
        })
    return zones

# for line-cross logic
_prev_centroids = {}
_line_counts    = {}

def _is_line_zone(z): return isinstance(z.get("points"), list) and len(z["points"]) == 2
def _sign(a, b, p):
    (x1,y1),(x2,y2) = a,b
    (x,y) = p
    return (x2-x1)*(y-y1) - (y2-y1)*(x-x1)

# ---------------- LIVE STREAM (draw + count + fill METRICS) ----------------
def mjpeg_generator():
    blank = np.zeros((480,640,3),dtype=np.uint8)
    global _prev_centroids

    last_push = time.time()
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

        try:
            frame = detector.process(frame)
        except:
            pass

        # line-crossing update
        try:
            tracks = detector.get_tracks()
            now_centroids = {}
            for x1,y1,x2,y2,tid,conf in tracks:
                cx = int((x1+x2)/2); cy = int((y1+y2)/2)
                now_centroids[tid] = (cx, cy)

            zones = _zones_from_db()
            for z in zones:
                if _is_line_zone(z):
                    _line_counts.setdefault(z["id"], 0)
            for z in zones:
                if not _is_line_zone(z): 
                    continue
                a = (int(z["points"][0]["x"]), int(z["points"][0]["y"]))
                b = (int(z["points"][1]["x"]), int(z["points"][1]["y"]))
                for tid, now_c in now_centroids.items():
                    prev_c = _prev_centroids.get(tid)
                    if prev_c is None: continue
                    s1 = _sign(a,b,prev_c)
                    s2 = _sign(a,b,now_c)
                    if s1 * s2 < 0:
                        _line_counts[z["id"]] += 1
            _prev_centroids = now_centroids
        except:
            pass

        # push to METRICS once per second
        try:
            if time.time() - last_push >= 1.0:
                snap = _current_live_snapshot()
                METRICS.append(snap)
                last_push = time.time()
        except:
            pass

        ok,buf=cv2.imencode(".jpg",frame)
        if not ok:
            time.sleep(0.01); continue
        yield(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+buf.tobytes()+b"\r\n")
        time.sleep(0.01)

@app.get("/video")
@jwt_required(locations=["cookies"])
def video(): 
    return Response(mjpeg_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")

@atexit.register
def cleanup(): 
    stop_stream()

# ---------------- ZONES API (CRUD) ----------------
def valid_points(pts):
    # keep helper, but validate normalized output
    return isinstance(pts, list) and len(_normalize_points(pts)) >= 2

@app.get("/api/zones")
@jwt_required(locations=["cookies"])
def zones_list():
    # Return normalized points always
    return jsonify(_zones_from_db())

@app.post("/api/zones")
@role_required("admin")
def zone_create():
    data = request.get_json() or {}
    # supports rare environments lacking str.trim
    name = (data.get("name") or "").trim() if hasattr("", "trim") else (data.get("name") or "").strip()
    pts = _normalize_points(data.get("points", []))
    if not name or len(pts) < 2:
        return jsonify({"ok": False, "message": "Invalid zone"}), 400
    get_db().execute("INSERT INTO zones(name,points) VALUES(?,?)", (name, json.dumps(pts)))
    get_db().commit()
    log_event("INFO", "zone_create", {"name": name, "points_len": len(pts)})
    return jsonify({"ok": True})

@app.put("/api/zones/<int:id>")
@role_required("admin")
def zone_update(id):
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    pts  = _normalize_points(data.get("points", []))
    if not name or len(pts) < 2:
        return jsonify({"ok": False, "message": "Invalid zone"}), 400

    db = get_db()
    if not db.execute("SELECT 1 FROM zones WHERE id=?", (id,)).fetchone():
        return jsonify({"ok": False, "message": "Not found"}), 404

    db.execute("UPDATE zones SET name=?, points=? WHERE id=?", (name, json.dumps(pts), id))
    db.commit()
    log_event("INFO", "zone_update", {"id": id, "name": name, "points_len": len(pts)})
    return jsonify({"ok": True})

@app.delete("/api/zones/<int:id>")
@role_required("admin")
def zone_delete(id):
    db=get_db()
    if not db.execute("SELECT id FROM zones WHERE id=?",(id,)).fetchone():
        return jsonify({"ok":False,"message":"Not found"}),404
    db.execute("DELETE FROM zones WHERE id=?", (id,)); db.commit()
    log_event("INFO", "zone_delete", {"id": id})
    return jsonify({"ok":True})

# ---------------- Counting APIs ----------------
@app.post("/api/count/image")
@jwt_required(locations=["cookies"])
def count_image_api():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "file missing"}), 400
    raw = request.files["file"].read()
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"ok": False, "message": "bad image"}), 400

    _ = detector.process(img.copy())
    tracks = detector.get_tracks()

    zones = _zones_from_db()
    per_zone = {}
    for z in zones:
        per_zone[z["name"]] = unique_ids_in_zone(z["points"], tracks)

    report = {
        "mode": "image",
        "total": len(tracks),
        "per_zone": per_zone,
        "tracks": [{"id": t[4], "bbox": [t[0],t[1],t[2],t[3]]} for t in tracks]
    }
    log_event("INFO", "count_image", {"total": report["total"]})
    return jsonify(report)

@app.post("/api/count/video")
@jwt_required(locations=["cookies"])
def count_video_api():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "file missing"}), 400
    f = request.files["file"]
    fname = os.path.basename(f.filename)
    ext = os.path.splitext(fname)[1].lower()
    if ext not in [".mp4",".avi",".mkv",".mov"]:
        return jsonify({"ok": False, "message": "unsupported video"}), 400
    path = os.path.join(UPLOAD_DIR, f"count_{fname}")
    f.save(path)

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return jsonify({"ok": False, "message": "cannot open video"}), 400

    zones = _zones_from_db()
    last_tracks = []

    while True:
        ok, frame = cap.read()
        if not ok: break
        _ = detector.process(frame)
        last_tracks = detector.get_tracks()
    cap.release()

    per_zone = {z["name"]: 0 for z in zones}
    for z in zones:
        per_zone[z["name"]] = unique_ids_in_zone(z["points"], last_tracks)

    report = {
        "mode": "video",
        "path": path,
        "total": len(last_tracks),
        "per_zone": per_zone,
        "tracks": [{"id": t[4], "bbox": [t[0],t[1],t[2],t[3]]} for t in last_tracks]
    }
    log_event("INFO", "count_video", {"total": report["total"], "file": fname})
    return jsonify(report)

@app.get("/api/count/live")
@jwt_required(locations=["cookies"])
def live_counts():
    tracks = detector.get_tracks()
    zones = _zones_from_db()

    per_zone = {}
    for z in zones:
        if len(z["points"]) >= 3:
            per_zone[z["name"]] = unique_ids_in_zone(z["points"], tracks)
        else:
            per_zone[z["name"]] = _line_counts.get(z["id"], 0)

    stats = { "total": len(tracks), "per_zone": per_zone, "source": _source_mode }
    return jsonify(stats)

# ---------------- Settings (persist alert threshold) ----------------
@app.get("/api/settings")
@jwt_required(locations=["cookies"])
def get_settings():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key='alert_threshold'").fetchone()
    thr = int(row["value"]) if row else 20
    return jsonify({"alert_threshold": thr})

@app.post("/api/settings")
@jwt_required(locations=["cookies"])
def set_settings():
    data = request.get_json() or {}
    thr = int(data.get("alert_threshold", 20))
    db = get_db()
    db.execute("INSERT INTO settings(key,value) VALUES('alert_threshold',?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(thr),))
    db.commit()
    log_event("INFO", "settings_update", {"alert_threshold": thr})
    return jsonify({"ok": True})

# ---------------- SSE live stream ----------------
from flask import stream_with_context
def _current_live_snapshot():
    tracks = detector.get_tracks()
    zones = _zones_from_db()
    total = len(tracks)

    per_zone = {}
    for z in zones:
        if len(z["points"]) >= 3:
            per_zone[z["name"]] = unique_ids_in_zone(z["points"], tracks)
        else:
            per_zone[z["name"]] = _line_counts.get(z["id"], 0)

    centers = []
    st = detector.get_state()
    fw, fh = max(1, st.frame_w), max(1, st.frame_h)
    for x1,y1,x2,y2,tid,conf in tracks:
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        centers.append({"x": float(cx)/fw, "y": float(cy)/fh})

    return { "total_people": total, "zones": per_zone, "centers": centers, "timestamp": int(time.time()) }

@app.get("/api/live")
@jwt_required(locations=["cookies"])
def api_live():
    @stream_with_context
    def gen():
        while True:
            payload = _current_live_snapshot()
            yield "data: " + json.dumps(payload, separators=(",",":")) + "\n\n"
            time.sleep(0.5)
    resp = Response(gen(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Connection"] = "keep-alive"
    return resp

# ---- Cameras API ----
@app.get("/api/cameras")
@role_required("admin")
def api_cameras_list():
    rows = get_db().execute(
        "SELECT id,name,rtsp_url,is_active FROM cameras ORDER BY id DESC"
    ).fetchall()
    out = [dict(r) for r in rows]
    return jsonify(out)

@app.post("/api/cameras")
@role_required("admin")
def api_cameras_create():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    rtsp_url = (data.get("rtsp_url") or "").strip()
    is_active = 1 if data.get("is_active", True) else 0
    if not name:
        return jsonify({"ok": False, "message": "Name required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO cameras(name,rtsp_url,is_active) VALUES(?,?,?)",
        (name, rtsp_url, is_active),
    )
    db.commit()
    cam_id = cur.lastrowid
    log_event("INFO", "camera_create", {"id": cam_id, "name": name})
    return jsonify({"ok": True, "id": cam_id})

@app.put("/api/cameras/<int:cam_id>")
@role_required("admin")
def api_cameras_update(cam_id):
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    rtsp_url = (data.get("rtsp_url") or "").strip()
    is_active = 1 if data.get("is_active", True) else 0
    db = get_db()
    if not db.execute("SELECT id FROM cameras WHERE id=?", (cam_id,)).fetchone():
        return jsonify({"ok": False, "message": "Not found"}), 404
    db.execute(
        "UPDATE cameras SET name=?, rtsp_url=?, is_active=? WHERE id=?",
        (name, rtsp_url, is_active, cam_id),
    )
    db.commit()
    log_event("INFO", "camera_update", {"id": cam_id})
    return jsonify({"ok": True})

@app.delete("/api/cameras/<int:cam_id>")
@role_required("admin")
def api_cameras_delete(cam_id):
    db = get_db()
    if not db.execute("SELECT id FROM cameras WHERE id=?", (cam_id,)).fetchone():
        return jsonify({"ok": False, "message": "Not found"}), 404
    db.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
    db.commit()
    log_event("INFO", "camera_delete", {"id": cam_id})
    return jsonify({"ok": True})

@app.post("/api/camera/start_by_id")
@role_required("admin")
def api_camera_start_by_id():
    cam_id = int((request.args.get("id") or "0"))
    row = get_db().execute(
        "SELECT rtsp_url FROM cameras WHERE id=?", (cam_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "message": "Camera not found"}), 404
    # start stream with RTSP (or fallback to webcam if empty)
    src = row["rtsp_url"] or os.getenv("CAMERA_INDEX", "0")
    global _stream,_source_mode,_still_frame,_source_path
    stop_stream()
    _still_frame = None
    _stream = VideoStream(src).start()
    _source_mode = "rtsp" if row["rtsp_url"] else "webcam"
    _source_path = row["rtsp_url"]
    log_event("INFO", "camera_start_by_id", {"id": cam_id, "src": src})
    return jsonify({"ok": True})

@app.post("/api/camera/stop_by_id")
@role_required("admin")
def api_camera_stop_by_id():
    stop_stream()
    log_event("INFO", "camera_stop_by_id", {})
    return jsonify({"ok": True})

# ---- Logs API (read-only) ----
@app.get("/api/logs")
@role_required("admin")
def api_logs():
    q = (request.args.get("q") or "").strip()
    level = (request.args.get("level") or "").strip().upper()
    date_from = (request.args.get("from") or "").strip()
    date_to = (request.args.get("to") or "").strip()
    limit = int(request.args.get("limit", "100"))

    sql = "SELECT id, ts, level, actor_email, action, meta_json FROM logs WHERE 1=1"
    params = []
    if level:
        sql += " AND level=?"; params.append(level)
    if q:
        sql += " AND (action LIKE ? OR meta_json LIKE ? OR actor_email LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if date_from:
        sql += " AND ts >= ?"; params.append(date_from)
    if date_to:
        sql += " AND ts <= ?"; params.append(date_to)
    sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)

    rows = get_db().execute(sql, tuple(params)).fetchall()
    out = [dict(r) for r in rows]
    return jsonify(out)

# ---- Reports API ----
@app.get("/api/reports")
@role_required("admin")
def api_reports_list():
    rows = get_db().execute(
        "SELECT id, ts_from, ts_to, kind, path, note, created_at FROM reports ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/reports/<int:rid>")
@role_required("admin")
def api_reports_download(rid):
    row = get_db().execute(
        "SELECT path, kind FROM reports WHERE id=?", (rid,)
    ).fetchone()
    if not row or not os.path.exists(row["path"]):
        return jsonify({"ok": False, "message": "Not found"}), 404
    fname = os.path.basename(row["path"])
    return send_file(row["path"], as_attachment=True, download_name=fname)

@app.delete("/api/reports/<int:rid>")
@role_required("admin")
def api_reports_delete(rid):
    db = get_db()
    row = db.execute("SELECT path FROM reports WHERE id=?", (rid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "message": "Not found"}), 404
    try:
        if os.path.exists(row["path"]): os.remove(row["path"])
    except Exception:
        pass
    db.execute("DELETE FROM reports WHERE id=?", (rid,))
    db.commit()
    log_event("INFO", "report_delete", {"id": rid})
    return jsonify({"ok": True})

# ---------------- Exports (CSV / PDF) ----------------
@app.get("/api/export/csv")
@jwt_required(locations=["cookies"])
def export_csv():
    minutes = int(request.args.get("minutes", "15"))
    cutoff = int(time.time()) - minutes*60

    rows = [m for m in list(METRICS) if m["timestamp"] >= cutoff]
    zone_names = sorted({n for m in rows for n in (m.get("zones") or {}).keys()})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp","time","total"] + zone_names)
    for m in rows:
        ts = m["timestamp"]
        timestr = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        z = m.get("zones") or {}
        writer.writerow([ts, timestr, m.get("total_people",0)] + [ z.get(name,0) for name in zone_names ])
    csv_data = output.getvalue()

    # persist to /uploads/reports
    ts_to = int(time.time()); ts_from = ts_to - minutes*60
    fname = f"crowdcount_{ts_from}_{ts_to}.csv"
    fpath = os.path.join(REPORT_DIR, fname)
    with open(fpath, "w", newline="", encoding="utf-8") as fh:
        fh.write(csv_data)

    db = get_db()
    db.execute(
        "INSERT INTO reports(ts_from, ts_to, kind, path, note) VALUES(?,?,?,?,?)",
        (ts_from, ts_to, "csv", fpath, f"Last {minutes} minutes")
    )
    db.commit()

    log_event("INFO", "export_csv", {"minutes": minutes, "rows": len(rows), "path": fpath})
    return send_file(fpath, as_attachment=True, download_name=fname, mimetype="text/csv")

@app.get("/api/export/pdf")
@jwt_required(locations=["cookies"])
def export_pdf():
    minutes = int(request.args.get("minutes", "15"))
    cutoff = int(time.time()) - minutes*60
    rows = [m for m in list(METRICS) if m["timestamp"] >= cutoff]
    ts_to = int(time.time()); ts_from = ts_to - minutes*60
    fname = f"crowdcount_{ts_from}_{ts_to}.pdf"
    fpath = os.path.join(REPORT_DIR, fname)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.lib.units import cm

        c = pdfcanvas.Canvas(fpath, pagesize=A4)
        w, h = A4
        c.setTitle("CrowdCount Report")

        c.setFont("Helvetica-Bold", 16)
        c.drawString(2*cm, h-2*cm, "CrowdCount – Summary Report")

        c.setFont("Helvetica", 10)
        c.drawString(2*cm, h-2.8*cm, f"Window: last {minutes} minutes")
        c.drawString(2*cm, h-3.3*cm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        totals = [m.get("total_people",0) for m in rows]
        avg = round(sum(totals)/len(totals),2) if totals else 0
        peak = max(totals) if totals else 0
        c.drawString(2*cm, h-4.3*cm, f"Average people: {avg}")
        c.drawString(2*cm, h-4.8*cm, f"Peak people: {peak}")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(2*cm, h-6*cm, "Time")
        c.drawString(6*cm, h-6*cm, "Total")
        y = h-6.5*cm
        c.setFont("Helvetica", 10)
        for m in rows[:30]:
            c.drawString(2*cm, y, datetime.fromtimestamp(m["timestamp"]).strftime("%H:%M:%S"))
            c.drawString(6*cm, y, str(m.get("total_people",0)))
            y -= 0.5*cm
            if y < 2*cm:
                c.showPage(); y = h-2*cm

        c.showPage(); c.save()

        db = get_db()
        db.execute(
            "INSERT INTO reports(ts_from, ts_to, kind, path, note) VALUES(?,?,?,?,?)",
            (ts_from, ts_to, "pdf", fpath, f"Last {minutes} minutes")
        )
        db.commit()

        log_event("INFO", "export_pdf", {"minutes": minutes, "rows": len(rows), "path": fpath})
        return send_file(fpath, as_attachment=True, download_name=fname, mimetype="application/pdf")
    except Exception as e:
        log_event("WARN", "export_pdf_failed_fallback_csv", {"minutes": minutes, "error": str(e)})
        return redirect(url_for("export_csv", minutes=minutes))

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
