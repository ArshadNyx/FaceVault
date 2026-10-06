"""
Face Engine - shared detection, alignment, quality gating and matching.

Pipeline (all through OpenCV, no extra runtime dependencies):
  YuNet  -> face box + 5 landmarks
  SFace  -> landmark-aligned 112x112 crop -> 128-d embedding
Embeddings are L2-normalised, so a dot product is the cosine similarity.
"""

import hashlib
import math
import os
import urllib.request
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    "detector": (
        "face_detection_yunet_2023mar.onnx",
        f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "recognizer": (
        "face_recognition_sface_2021dec.onnx",
        f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}

EMBEDDING_SIZE = 128

# Cosine similarity a probe must reach to match an enrolled user, and how far
# the best user must lead the runner-up. On the 6000 LFW pairs this pipeline
# scores 99.45%; no impostor pair exceeds 0.39, so 0.5 leaves a safety margin.
DEFAULT_THRESHOLD = 0.5
MIN_THRESHOLD, MAX_THRESHOLD = 0.3, 0.8
MATCH_MARGIN = 0.05

# Logistic mapping from cosine score to P(same person), fitted on LFW pairs.
_CONF_SLOPE, _CONF_MIDPOINT = 33.0, 0.326

_DETECT_MAX_SIDE = 1280


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_models() -> Dict[str, str]:
    """Return model paths, downloading (and verifying) any that are missing."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    paths = {}
    for name, (filename, url, sha) in MODELS.items():
        path = os.path.join(MODEL_DIR, filename)
        if not os.path.exists(path):
            print(f"Downloading {filename} ...")
            tmp = path + ".part"
            urllib.request.urlretrieve(url, tmp)
            if _sha256(tmp) != sha:
                os.remove(tmp)
                raise RuntimeError(f"Checksum mismatch downloading {filename}")
            os.replace(tmp, path)
        elif _sha256(path) != sha:
            raise RuntimeError(f"{path} is corrupt; delete it and restart to re-download")
        paths[name] = path
    return paths


class Face:
    """A detected face: YuNet row = [x, y, w, h, 5 x (lx, ly), score]."""

    def __init__(self, row: np.ndarray):
        self.row = row

    @property
    def box(self) -> Tuple[int, int, int, int]:
        x, y, w, h = self.row[:4]
        return int(x), int(y), int(w), int(h)

    @property
    def score(self) -> float:
        return float(self.row[14])

    @property
    def landmarks(self) -> np.ndarray:
        """(5, 2): right eye, left eye, nose tip, right mouth, left mouth."""
        return self.row[4:14].reshape(5, 2)


class FaceEngine:
    # Quality limits as (authentication, enrollment); enrollment is stricter
    # because a poor template degrades every later comparison.
    MIN_DET_SCORE = (0.80, 0.85)
    MIN_FACE_SIZE = (80, 110)
    MAX_ROLL_DEG = (30.0, 20.0)
    MAX_YAW = (0.40, 0.28)       # nose offset from eye midpoint / eye distance
    PITCH_RANGE = ((0.20, 0.95), (0.30, 0.85))  # nose height between eyes and mouth
    MIN_SHARPNESS = (20.0, 40.0)  # Laplacian variance of the aligned crop
    BRIGHTNESS_RANGE = ((35, 225), (50, 215))

    def __init__(self):
        paths = ensure_models()
        self.detector = cv2.FaceDetectorYN.create(
            paths["detector"], "", (320, 320),
            score_threshold=0.6, nms_threshold=0.3, top_k=5000,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(paths["recognizer"], "")

    # -- detection ---------------------------------------------------------
    def detect(self, frame: np.ndarray, min_size: int = 50) -> List[Face]:
        """Detect faces, largest first."""
        h, w = frame.shape[:2]
        scale = min(1.0, _DETECT_MAX_SIDE / max(h, w))
        img = frame if scale == 1.0 else cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        self.detector.setInputSize((img.shape[1], img.shape[0]))
        _, rows = self.detector.detect(img)
        if rows is None:
            return []
        faces = []
        for row in rows:
            row = row.copy()
            row[:14] /= scale
            if row[2] >= min_size and row[3] >= min_size:
                faces.append(Face(row))
        faces.sort(key=lambda f: f.row[2] * f.row[3], reverse=True)
        return faces

    # -- quality + embedding -------------------------------------------------
    def quality_issue(self, frame: np.ndarray, face: Face, aligned: np.ndarray,
                      enrolling: bool = False) -> Optional[str]:
        """Return a user-facing reason the face is unusable, or None if it is fine."""
        lvl = 1 if enrolling else 0
        x, y, w, h = face.box
        fh, fw = frame.shape[:2]

        if face.score < self.MIN_DET_SCORE[lvl]:
            return "Face not clear - look at the camera"
        if min(w, h) < self.MIN_FACE_SIZE[lvl]:
            return "Move closer to the camera"
        if x < 0 or y < 0 or x + w > fw or y + h > fh:
            return "Keep your whole face in the frame"

        r_eye, l_eye, nose, r_mouth, l_mouth = face.landmarks
        eye_vec = l_eye - r_eye
        eye_dist = float(np.linalg.norm(eye_vec))
        if eye_dist < 1e-6:
            return "Face not clear - look at the camera"
        roll = abs(math.degrees(math.atan2(eye_vec[1], eye_vec[0])))
        if roll > self.MAX_ROLL_DEG[lvl]:
            return "Keep your head level"
        eye_mid = (l_eye + r_eye) / 2
        mouth_mid = (l_mouth + r_mouth) / 2
        # Measure along the face's own axes so head roll doesn't read as yaw/pitch.
        ax = eye_vec / eye_dist
        ay = np.array([-ax[1], ax[0]])
        yaw = abs(float(np.dot(nose - eye_mid, ax))) / eye_dist
        if yaw > self.MAX_YAW[lvl]:
            return "Face the camera directly"
        face_len = float(np.dot(mouth_mid - eye_mid, ay))
        lo, hi = self.PITCH_RANGE[lvl]
        if face_len <= 1e-6 or not lo <= float(np.dot(nose - eye_mid, ay)) / face_len <= hi:
            return "Face the camera directly"

        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        lo, hi = self.BRIGHTNESS_RANGE[lvl]
        brightness = float(gray.mean())
        if brightness < lo:
            return "Too dark - add more light"
        if brightness > hi:
            return "Too bright - reduce the light"
        if cv2.Laplacian(gray, cv2.CV_64F).var() < self.MIN_SHARPNESS[lvl]:
            return "Image is blurry - hold still"
        return None

    def align(self, frame: np.ndarray, face: Face) -> np.ndarray:
        return self.recognizer.alignCrop(frame, face.row)

    def embed(self, aligned: np.ndarray) -> np.ndarray:
        """Unit-length embedding, averaged with the mirrored crop for stability."""
        feat = self.recognizer.feature(aligned).flatten()
        feat = feat + self.recognizer.feature(cv2.flip(aligned, 1)).flatten()
        return (feat / (np.linalg.norm(feat) + 1e-12)).astype(np.float64)

    def analyze(self, frame: np.ndarray, face: Face,
                enrolling: bool = False) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """Quality-gate a face and embed it. Returns (embedding, None) or (None, reason)."""
        aligned = self.align(frame, face)
        issue = self.quality_issue(frame, face, aligned, enrolling)
        if issue:
            return None, issue
        return self.embed(aligned), None


_engine: Optional[FaceEngine] = None


def get_engine() -> FaceEngine:
    """Get or create the shared engine (the models are loaded once)."""
    global _engine
    if _engine is None:
        _engine = FaceEngine()
    return _engine


# -- matching ------------------------------------------------------------------
def load_templates(storage) -> Dict[str, np.ndarray]:
    """Load every user's template as a (samples, 128) array of unit embeddings."""
    templates = {}
    for username in storage.list_users():
        enc = storage.load_encoding(username)
        if enc is None:
            continue
        enc = np.atleast_2d(enc)
        if enc.shape[-1] != EMBEDDING_SIZE:
            print(f"User '{username}' has an outdated face template and must re-register")
            continue
        templates[username] = enc
    return templates


def user_score(embedding: np.ndarray, template: np.ndarray) -> float:
    """Similarity to a user: mean of the two best-matching enrolled samples."""
    sims = np.sort(template @ embedding)
    return float(sims[-2:].mean())


def best_match(embedding: np.ndarray, templates: Dict[str, np.ndarray]) -> Tuple[Optional[str], float, float]:
    """Return (best user, best score, runner-up score) over all enrolled users."""
    scores = sorted(((user_score(embedding, t), u) for u, t in templates.items()), reverse=True)
    if not scores:
        return None, 0.0, 0.0
    runner_up = scores[1][0] if len(scores) > 1 else 0.0
    return scores[0][1], scores[0][0], runner_up


def is_match(score: float, runner_up: float, threshold: float) -> bool:
    return score >= threshold and score - runner_up >= MATCH_MARGIN


def score_to_confidence(score: float) -> float:
    """Map a cosine score to an estimated probability of being the same person."""
    return 1.0 / (1.0 + math.exp(-_CONF_SLOPE * (score - _CONF_MIDPOINT)))
