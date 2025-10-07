# app.py
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional

import cv2
import numpy as np
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId

# load .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "crowdcount_db")
JWT_SECRET = os.getenv("JWT_SECRET", "change_this")
JWT_ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

if not MONGO_URI:
    raise RuntimeError("Please set MONGO_URI in .env before running")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -----------------------
# Connect to MongoDB
# -----------------------
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_col = db["users"]
zones_col = db["zones"]

# ensure username unique index
try:
    users_col.create_index("username", unique=True)
except Exception:
    pass

# print connection success
try:
    # ping the server
    client.admin.command("ping")
    print("✅ MongoDB connected successfully.")
except Exception as e:
    print("❌ MongoDB connection failed:", e)

# -----------------------
# Pydantic models
# -----------------------
class RegisterModel(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginModel(BaseModel):
    username: str
    password: str


class ZoneModel(BaseModel):
    name: str
    points: List[List[int]]
    camera_id: Optional[str] = "cam1"


# -----------------------
# Auth helpers
# -----------------------
def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(username: str, minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    payload = {"sub": username, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return token


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = credentials.credentials
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = users_col.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"username": user["username"], "id": str(user["_id"])}


# -----------------------
# Pages
# -----------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


# -----------------------
# Video stream (MJPEG)
# -----------------------
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            _, buf = cv2.imencode(".jpg", blank)
            frame_bytes = buf.tobytes()
        else:
            _, buf = cv2.imencode(".jpg", frame)
            frame_bytes = buf.tobytes()
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        time.sleep(0.03)


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


# -----------------------
# Auth API
# -----------------------
@app.post("/api/auth/register")
def api_register(payload: RegisterModel):
    existing = users_col.find_one({"username": payload.username})
    if existing:
        return JSONResponse({"detail": "username already exists"}, status_code=400)
    hashed = hash_password(payload.password)
    doc = {
        "username": payload.username,
        "password": hashed,
        "email": payload.email or "",
        "created_at": time.time(),
    }
    users_col.insert_one(doc)
    return {"status": "ok"}


@app.post("/api/auth/login")
def api_login(payload: LoginModel):
    user = users_col.find_one({"username": payload.username})
    if not user or not verify_password(payload.password, user["password"]):
        return JSONResponse({"detail": "invalid credentials"}, status_code=401)
    token = create_access_token(user["username"])
    return {"access_token": token, "token_type": "bearer"}


# -----------------------
# Zones API (protected)
# -----------------------
@app.post("/api/zones")
def api_save_zone(payload: ZoneModel, user=Depends(get_current_user)):
    doc = {
        "name": payload.name,
        "points": payload.points,
        "owner": user["username"],
        "camera_id": payload.camera_id,
        "created_at": time.time(),
    }
    res = zones_col.insert_one(doc)
    return {"status": "ok", "id": str(res.inserted_id)}


@app.get("/api/zones")
def api_get_zones(user=Depends(get_current_user)):
    docs = list(zones_col.find({"owner": user["username"]}))
    out = []
    for d in docs:
        out.append({
            "id": str(d["_id"]),
            "name": d.get("name"),
            "points": d.get("points"),
            "camera_id": d.get("camera_id"),
            "created_at": d.get("created_at"),
        })
    return {"zones": out}


@app.delete("/api/zones/{zone_id}")
def api_delete_zone(zone_id: str, user=Depends(get_current_user)):
    try:
        oid = ObjectId(zone_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid zone id")
    res = zones_col.delete_one({"_id": oid, "owner": user["username"]})
    if res.deleted_count == 1:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="zone not found")
