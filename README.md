# Face Unlock System

A professional biometric face authentication system built with **FastAPI**, **OpenCV**, and a sleek dark-themed web UI. Register faces, authenticate in real-time via webcam, manage users, and integrate face auth into your own apps via REST API.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Running the Server](#running-the-server)
- [Using the Web UI](#using-the-web-ui)
- [REST API Documentation](#rest-api-documentation)
- [WebSocket Real-Time Events](#websocket-real-time-events)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Security](#security)

---

## Features

- Real-time face detection and authentication via webcam
- Encrypted face data storage (Fernet/AES-256 + PBKDF2 key derivation)
- Multi-user registration and management
- REST API for integrating face auth into external applications
- WebSocket for real-time auth event streaming
- MJPEG video stream endpoint
- Configurable matching threshold
- Activity logging
- Auto-lock on inactivity
- Elegant dark-themed web interface with scan animations

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (Web UI)                  │
│   HTML/CSS/JS  ←→  REST API  ←→  WebSocket          │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                FastAPI Server (server.py)             │
│                                                      │
│  ┌──────────────┐ ┌───────────────┐ ┌─────────────┐ │
│  │   Face        │ │   Face         │ │   Secure    │ │
│  │ Registration  │ │ Authentication │ │   Storage   │ │
│  │               │ │                │ │  (Fernet)   │ │
│  └──────┬───────┘ └───────┬────────┘ └──────┬──────┘ │
│         │                 │                  │        │
│         └─────────────────┼──────────────────┘        │
│                           │                           │
│                  OpenCV (Webcam + Haar Cascade)        │
└───────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  face_data/  │
                    │ (encrypted)  │
                    └─────────────┘
```

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- pip
- A webcam (built-in or USB)

### Step 1: Clone the repository

```bash
git clone https://github.com/ArshadNyx/FaceVault.git
cd face-unlock-system
```

### Step 2: Create a virtual environment (recommended)

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

**Dependencies installed:**

| Package | Purpose |
|---------|---------|
| `opencv-python` | Face detection via Haar Cascade |
| `opencv-contrib-python` | Additional OpenCV modules |
| `numpy` | Numerical computing for face encodings |
| `Pillow` | Image processing |
| `cryptography` | Fernet encryption for secure face data storage |
| `mediapipe` | Alternative face detection support |
| `fastapi` | Web framework / REST API server |
| `uvicorn` | ASGI server for FastAPI |
| `python-multipart` | Form data handling |
| `websockets` | WebSocket support |

---

## Running the Server

### Option 1: Using the run script

```bash
chmod +x run.sh
./run.sh
```

### Option 2: Direct command

```bash
python server.py
```

### Option 3: With uvicorn directly

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at **http://localhost:8000**.

> **Note:** If accessing from another device on your network, use `http://<your-ip>:8000`. The camera will use server-side MJPEG streaming in this case since `getUserMedia` requires HTTPS or localhost.

---

## Using the Web UI

Open **http://localhost:8000** in your browser. The UI has 5 tabs:

### Authentication Tab
1. Click **Start Camera** to activate the webcam
2. Click **Authenticate** to begin face scanning
3. When a registered face is detected, the system unlocks automatically and stops scanning
4. Click **Lock** to re-lock the system

### Register Tab
1. Click **Start Camera** to activate the webcam
2. Click **Capture Face** to take a snapshot
3. Enter a **username**
4. Click **Register Face** to save

### Users Tab
- View all registered users
- Delete users with the trash icon
- See system stats (user count, event count, encryption standard)

### Activity Tab
- View a chronological log of all authentication attempts, registrations, and system events
- Click **Refresh** to update

### Settings Tab
- **Camera Index**: Select which camera to use (0 = default)
- **Matching Threshold**: Adjust strictness (lower = stricter, fewer false positives)
- **Auto-lock**: Enable/disable automatic locking after inactivity
- **Timeout**: Seconds of inactivity before auto-lock
- **Show Confidence**: Toggle confidence score display

---

## REST API Documentation

All endpoints return JSON. Base URL: `http://localhost:8000`

### Authentication

#### `POST /api/auth/authenticate`

Authenticate a face from a base64-encoded image.

**Request body:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

**Response (success):**
```json
{
  "authenticated": true,
  "username": "john",
  "confidence": 0.84,
  "message": "Authentication successful"
}
```

**Response (failure):**
```json
{
  "authenticated": false,
  "username": null,
  "confidence": 0,
  "message": "No face detected"
}
```

---

#### `POST /api/auth/lock`

Lock the system. No request body needed.

**Response:**
```json
{
  "status": "locked"
}
```

---

#### `GET /api/auth/status`

Get the current authentication status.

**Response:**
```json
{
  "locked": false,
  "user": "john",
  "confidence": 0.84,
  "last_auth_time": "14:32:05"
}
```

---

### User Registration

#### `POST /api/register`

Register a new user with a face image.

**Request body:**
```json
{
  "username": "john",
  "image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully"
}
```

**Errors:**
- `400` — Username is empty, too short, or image is invalid
- Face not detected in the image

---

#### `GET /api/users`

List all registered users.

**Response:**
```json
{
  "users": ["john", "jane", "admin"]
}
```

---

#### `DELETE /api/users/{username}`

Delete a registered user.

**Response:**
```json
{
  "success": true
}
```

---

### Camera

#### `POST /api/camera/start`

Start the server-side camera (OpenCV).

**Response:**
```json
{
  "status": "ok"
}
```

---

#### `POST /api/camera/stop`

Stop and release the server-side camera.

**Response:**
```json
{
  "status": "ok"
}
```

---

#### `GET /api/camera/frame`

Get a single frame as a base64-encoded JPEG.

**Response:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

---

#### `GET /api/camera/stream`

MJPEG video stream. Use directly in an `<img>` tag:

```html
<img src="http://localhost:8000/api/camera/stream" />
```

---

### Settings

#### `GET /api/settings`

Get current settings.

**Response:**
```json
{
  "camera_index": 0,
  "threshold": 0.5,
  "auto_lock": true,
  "auto_lock_timeout": 60,
  "show_confidence": true
}
```

---

#### `PUT /api/settings`

Update settings. Only include the fields you want to change.

**Request body:**
```json
{
  "threshold": 0.4,
  "auto_lock_timeout": 120
}
```

**Response:** Returns the full updated settings object.

---

### Activity Log

#### `GET /api/activity`

Get the activity log (last 100 events).

**Response:**
```json
{
  "logs": [
    {
      "time": "2026-03-22 14:32:05",
      "action": "Authentication",
      "detail": "User 'john' authenticated (84%)",
      "status": "success"
    }
  ]
}
```

---

## WebSocket Real-Time Events

Connect to `ws://localhost:8000/ws` to receive real-time events.

**Auth event (pushed on successful authentication):**
```json
{
  "type": "auth",
  "success": true,
  "username": "john",
  "confidence": 0.84
}
```

**Lock event:**
```json
{
  "type": "lock",
  "locked": true
}
```

**Client can send pings:**
```
"ping" → receives {"type": "pong"}
```

### Example: Python WebSocket client

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "auth" and msg["success"]:
                print(f"User {msg['username']} authenticated!")

asyncio.run(listen())
```

### Example: JavaScript client

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'auth' && data.success) {
        console.log(`Authenticated: ${data.username}`);
    }
};
```

---

## Configuration

Settings are stored in `settings.json` in the project root.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `camera_index` | int | `0` | Which camera device to use |
| `threshold` | float | `0.5` | Face matching threshold (0.1–0.9, lower = stricter) |
| `auto_lock` | bool | `true` | Auto-lock after inactivity |
| `auto_lock_timeout` | int | `60` | Seconds before auto-lock triggers |
| `show_confidence` | bool | `true` | Display confidence percentage in UI |

---

## Project Structure

```
face-unlock-system/
├── server.py               # FastAPI backend — routes, camera, API
├── face_registration.py    # Face detection + encoding for registration
├── face_authentication.py  # Face matching against stored encodings
├── secure_storage.py       # Fernet-encrypted face data storage
├── static/
│   ├── index.html          # Single-page web application
│   ├── css/style.css       # Premium dark theme styles
│   └── js/app.js           # Frontend logic — camera, auth, UI
├── face_data/              # Encrypted face encodings (auto-created)
│   ├── encodings.enc       # Encrypted user face data
│   ├── salt.bin            # PBKDF2 salt
│   └── key.bin             # Derived encryption key
├── settings.json           # User settings (auto-created)
├── requirements.txt        # Python dependencies
├── run.sh                  # Launch script
└── README.md               # This file
```

---

## Security

- **Encryption**: All face encodings are encrypted at rest using Fernet symmetric encryption with PBKDF2-HMAC-SHA256 key derivation (480,000 iterations)
- **Local-only**: No face data is transmitted to any external server
- **No passwords stored**: Face data is the authentication factor; the system does not store or transmit user passwords
- **CORS**: Enabled for development; restrict `allow_origins` in production
- **HTTPS**: For production deployment, use a reverse proxy (nginx) with TLS certificates to enable `getUserMedia` in the browser

---

## Integration Example

### Authenticate a user from your own app

```python
import requests
import base64

# Read an image file
with open("photo.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

# Call the API
response = requests.post("http://localhost:8000/api/auth/authenticate", json={
    "image": f"data:image/jpeg;base64,{img_b64}"
})

result = response.json()
if result["authenticated"]:
    print(f"Welcome, {result['username']}! Confidence: {result['confidence']:.0%}")
else:
    print("Not recognized")
```

### Register a new user programmatically

```python
import requests
import base64

with open("face_photo.jpg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

response = requests.post("http://localhost:8000/api/register", json={
    "username": "new_user",
    "image": f"data:image/jpeg;base64,{img_b64}"
})

print(response.json())
# {"success": true, "message": "User registered successfully"}
```
