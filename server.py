"""
Face Unlock System - FastAPI Backend
Professional face authentication service with REST API support.
"""

import asyncio
import atexit
import base64
import json
import os
import signal
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from face_registration import FaceRegistration
from face_authentication import FaceAuthentication
from secure_storage import get_storage


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
class AppState:
    def __init__(self):
        self.camera: Optional[cv2.VideoCapture] = None
        self.camera_active = False
        self.face_reg = FaceRegistration()
        self.face_auth = FaceAuthentication()
        self.storage = get_storage()
        self.is_locked = True
        self.last_auth_user: Optional[str] = None
        self.last_auth_time: Optional[str] = None
        self.last_auth_confidence: float = 0.0
        self.auth_running = False
        self.settings = self._load_settings()
        self.activity_log: list[dict] = []
        self.ws_clients: list[WebSocket] = []

    def _load_settings(self) -> dict:
        defaults = {
            "camera_index": 0,
            "threshold": 0.5,
            "auto_lock": True,
            "auto_lock_timeout": 60,
            "show_confidence": True,
        }
        if os.path.exists("settings.json"):
            try:
                with open("settings.json") as f:
                    saved = json.load(f)
                defaults.update(saved)
            except Exception:
                pass
        return defaults

    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=2)

    def log_activity(self, action: str, detail: str, status: str = "info"):
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "detail": detail,
            "status": status,
        }
        self.activity_log.insert(0, entry)
        if len(self.activity_log) > 100:
            self.activity_log = self.activity_log[:100]

    def start_camera(self) -> bool:
        if self.camera_active and self.camera is not None:
            return True
        idx = self.settings.get("camera_index", 0)
        self.camera = cv2.VideoCapture(idx)
        if not self.camera.isOpened():
            self.camera = None
            return False
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.camera_active = True
        return True

    def stop_camera(self):
        self.camera_active = False
        # Small delay to let any active MJPEG generator exit its loop
        time.sleep(0.15)
        cam = self.camera
        self.camera = None
        if cam is not None:
            try:
                cam.release()
            except Exception:
                pass

    def get_frame(self):
        if self.camera is None or not self.camera_active:
            return None
        ret, frame = self.camera.read()
        return frame if ret else None


state = AppState()


# ---------------------------------------------------------------------------
# Ensure camera is ALWAYS released — even on Ctrl+C or crash
# ---------------------------------------------------------------------------
def _force_release_camera():
    """Release camera hardware no matter how the process exits."""
    if state.camera is not None:
        try:
            state.camera.release()
        except Exception:
            pass
        state.camera = None
    state.camera_active = False
    # Also release any OpenCV camera that might be lingering
    cv2.destroyAllWindows()

atexit.register(_force_release_camera)

def _signal_handler(sig, frame):
    _force_release_camera()
    raise SystemExit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _force_release_camera()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Face Unlock System",
    description="Professional face authentication service",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str
    image: str  # base64 encoded image


class SettingsUpdate(BaseModel):
    camera_index: Optional[int] = None
    threshold: Optional[float] = None
    auto_lock: Optional[bool] = None
    auto_lock_timeout: Optional[int] = None
    show_confidence: Optional[bool] = None


class AuthenticateRequest(BaseModel):
    image: str  # base64 encoded image


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def decode_base64_image(b64: str) -> np.ndarray:
    """Decode a base64-encoded image string to an OpenCV frame."""
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image")
    return frame


async def broadcast_ws(data: dict):
    """Send data to all connected WebSocket clients."""
    dead = []
    for ws in state.ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Routes – Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------------------------
# Routes – Camera
# ---------------------------------------------------------------------------
@app.post("/api/camera/start")
async def camera_start():
    ok = state.start_camera()
    if not ok:
        raise HTTPException(status_code=500, detail="Cannot open camera")
    state.log_activity("Camera", "Camera started", "success")
    return {"status": "ok"}


@app.post("/api/camera/stop")
async def camera_stop():
    state.stop_camera()
    state.log_activity("Camera", "Camera stopped", "info")
    return {"status": "ok"}


@app.get("/api/camera/frame")
async def camera_frame():
    """Return current camera frame as base64 JPEG."""
    frame = state.get_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame available")
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf).decode("utf-8")
    return {"image": f"data:image/jpeg;base64,{b64}"}


def gen_mjpeg():
    """Generator for MJPEG streaming."""
    while state.camera_active:
        frame = state.get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )
        time.sleep(0.033)  # ~30 fps


@app.get("/api/camera/stream")
async def camera_stream():
    """MJPEG video stream endpoint."""
    if not state.camera_active:
        state.start_camera()
    return StreamingResponse(
        gen_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ---------------------------------------------------------------------------
# Routes – Authentication
# ---------------------------------------------------------------------------
@app.post("/api/auth/authenticate")
async def authenticate(req: AuthenticateRequest):
    """Authenticate a face from a base64-encoded image."""
    try:
        frame = decode_base64_image(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    result = state.face_auth.authenticate_single_face(frame)
    if result and result.success:
        state.is_locked = False
        state.last_auth_user = result.username
        state.last_auth_confidence = result.confidence
        state.last_auth_time = datetime.now().strftime("%H:%M:%S")
        state.log_activity(
            "Authentication",
            f"User '{result.username}' authenticated ({result.confidence:.0%})",
            "success",
        )
        await broadcast_ws({
            "type": "auth",
            "success": True,
            "username": result.username,
            "confidence": result.confidence,
        })
        return {
            "authenticated": True,
            "username": result.username,
            "confidence": result.confidence,
            "message": result.message,
        }
    else:
        state.log_activity("Authentication", "Face not recognized", "warning")
        await broadcast_ws({"type": "auth", "success": False})
        return {
            "authenticated": False,
            "username": None,
            "confidence": 0,
            "message": result.message if result else "No face detected",
        }


@app.post("/api/auth/lock")
async def lock_system():
    state.is_locked = True
    state.last_auth_user = None
    state.log_activity("Security", "System locked", "info")
    await broadcast_ws({"type": "lock", "locked": True})
    return {"status": "locked"}


@app.get("/api/auth/status")
async def auth_status():
    return {
        "locked": state.is_locked,
        "user": state.last_auth_user,
        "confidence": state.last_auth_confidence,
        "last_auth_time": state.last_auth_time,
    }


# ---------------------------------------------------------------------------
# Routes – Registration
# ---------------------------------------------------------------------------
@app.post("/api/register")
async def register_user(req: RegisterRequest):
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")

    try:
        frame = decode_base64_image(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    success, message = state.face_reg.register_user_single_frame(username, frame)
    if success:
        # Reload auth encodings
        state.face_auth = FaceAuthentication()
        state.log_activity("Registration", f"User '{username}' registered", "success")
    else:
        state.log_activity("Registration", f"Failed: {message}", "error")

    return {"success": success, "message": message}


@app.get("/api/users")
async def list_users():
    users = state.face_reg.get_registered_users()
    return {"users": users}


@app.delete("/api/users/{username}")
async def delete_user(username: str):
    success, _ = state.face_reg.delete_user(username)
    if success:
        state.face_auth = FaceAuthentication()
        state.log_activity("User Management", f"User '{username}' deleted", "warning")
    return {"success": success}


# ---------------------------------------------------------------------------
# Routes – Settings
# ---------------------------------------------------------------------------
@app.get("/api/settings")
async def get_settings():
    return state.settings


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    updates = req.model_dump(exclude_none=True)
    state.settings.update(updates)
    state.save_settings()
    if "threshold" in updates:
        state.face_auth.threshold = updates["threshold"]
    state.log_activity("Settings", f"Updated: {', '.join(updates.keys())}", "info")
    return state.settings


# ---------------------------------------------------------------------------
# Routes – Activity log
# ---------------------------------------------------------------------------
@app.get("/api/activity")
async def get_activity():
    return {"logs": state.activity_log}


# ---------------------------------------------------------------------------
# WebSocket – Real-time updates
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            # Client can send ping
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if ws in state.ws_clients:
            state.ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
