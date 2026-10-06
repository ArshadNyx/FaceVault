"""
Face Authentication Module
This module handles face recognition and authentication by comparing
live camera input with stored facial embeddings (YuNet + SFace, see
face_engine.py).
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
from datetime import datetime
from secure_storage import get_storage
import face_engine
from face_engine import get_engine


class AuthenticationResult:
    """Class to hold authentication results."""
    
    def __init__(self, success: bool, username: str = "", confidence: float = 0.0, 
                 message: str = "", timestamp: str = "", face_location: Tuple[int, int, int, int] = None,
                 score: float = 0.0, face_evaluated: bool = False):
        self.success = success
        self.username = username
        self.confidence = confidence
        self.score = score  # raw cosine similarity to the best-matching user
        self.face_evaluated = face_evaluated  # a usable face was compared against users
        self.message = message
        self.timestamp = timestamp or datetime.now().isoformat()
        self.face_location = face_location
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'username': self.username,
            'confidence': self.confidence,
            'score': self.score,
            'message': self.message,
            'timestamp': self.timestamp,
            'face_location': self.face_location
        }


class FaceAuthentication:
    """
    Face authentication against enrolled users.
    Each user has several enrolled embeddings; a probe face must clear the
    similarity threshold and beat every other user by a margin.
    """
    
    DEFAULT_THRESHOLD = face_engine.DEFAULT_THRESHOLD
    
    def __init__(self, camera_index: int = 0, threshold: float = DEFAULT_THRESHOLD):
        self.camera_index = camera_index
        self.threshold = threshold
        self.video_capture: Optional[cv2.VideoCapture] = None
        self.storage = get_storage()
        self.is_running = False
        self.known_encodings: Dict[str, np.ndarray] = {}
        self.engine = get_engine()
        
        # Load known encodings
        self._load_known_encodings()
        
        print("Face authentication module initialized")
    
    def _load_known_encodings(self) -> None:
        """Load all known face templates from storage."""
        self.known_encodings = face_engine.load_templates(self.storage)
        print(f"Loaded {len(self.known_encodings)} registered users")
    
    def reload_encodings(self) -> None:
        """Reload known encodings from storage."""
        self._load_known_encodings()
    
    def start_camera(self) -> bool:
        """Start the video capture with optimized settings."""
        try:
            self.video_capture = cv2.VideoCapture(self.camera_index)
            if not self.video_capture.isOpened():
                print("Error: Could not open camera")
                return False
            
            # Optimized camera settings for high FPS
            self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video_capture.set(cv2.CAP_PROP_FPS, 30)
            self.video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer for low latency
            self.video_capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            
            # Warm up camera
            for _ in range(3):
                self.video_capture.read()
            
            self.is_running = True
            self.frame_count = 0
            print("Camera started (optimized mode)")
            return True
        except Exception as e:
            print(f"Error starting camera: {e}")
            return False
    
    def stop_camera(self) -> None:
        """Stop the video capture."""
        self.is_running = False
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from the camera."""
        if self.video_capture is None or not self.is_running:
            return None
        
        ret, frame = self.video_capture.read()
        if not ret:
            return None
        
        return frame
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces (x, y, width, height), largest first."""
        return [f.box for f in self.engine.detect(frame)]
    
    def get_face_encoding(self, frame: np.ndarray, face_location: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Embedding of the detected face at the given location, if it passes quality checks."""
        face = self._face_at(frame, face_location)
        if face is None:
            return None
        return self.engine.analyze(frame, face)[0]
    
    def _face_at(self, frame: np.ndarray, face_location: Tuple[int, int, int, int]):
        """Find the detected face whose centre lies closest to the given box."""
        x, y, w, h = face_location
        cx, cy = x + w / 2, y + h / 2
        for face in self.engine.detect(frame):
            fx, fy, fw, fh = face.box
            if fx <= cx <= fx + fw and fy <= cy <= fy + fh:
                return face
        return None
    
    def calculate_similarity(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        if encoding1.shape != encoding2.shape:
            return 0.0
        return float(np.dot(encoding1, encoding2))
    
    def compare_faces(self, encoding: np.ndarray) -> Tuple[Optional[str], float]:
        """Compare an embedding with all users. Returns (username or None, score)."""
        username, score, runner_up = face_engine.best_match(encoding, self.known_encodings)
        if username and face_engine.is_match(score, runner_up, self.threshold):
            return username, score
        return None, score
    
    def authenticate_single_face(self, frame: np.ndarray) -> AuthenticationResult:
        """
        Authenticate the most prominent face in the frame. Only the largest
        face counts, so a registered user in the background cannot unlock
        the system for whoever is in front of the camera.
        """
        faces = self.engine.detect(frame)
        if not faces:
            return AuthenticationResult(success=False, message="No face detected")
        
        face = faces[0]
        encoding, issue = self.engine.analyze(frame, face)
        if encoding is None:
            return AuthenticationResult(success=False, message=issue, face_location=face.box)
        
        if not self.known_encodings:
            return AuthenticationResult(success=False, message="No registered users",
                                        face_location=face.box)
        
        username, score = self.compare_faces(encoding)
        confidence = face_engine.score_to_confidence(score)
        if username:
            return AuthenticationResult(
                success=True, username=username, confidence=confidence, score=score,
                message=f"Access granted for {username}",
                face_location=face.box, face_evaluated=True
            )
        return AuthenticationResult(
            success=False, confidence=confidence, score=score,
            message="Face not recognized", face_location=face.box, face_evaluated=True
        )
    
    def authenticate_frame(self, frame: np.ndarray) -> List[AuthenticationResult]:
        """Authenticate the frame (kept for compatibility; one result per frame)."""
        return [self.authenticate_single_face(frame)]
    
    def set_threshold(self, threshold: float) -> None:
        """Set the face matching threshold."""
        self.threshold = max(face_engine.MIN_THRESHOLD, min(face_engine.MAX_THRESHOLD, threshold))
    
    def get_registered_users(self) -> List[str]:
        """Get list of registered users."""
        return list(self.known_encodings.keys())
    
    def __del__(self):
        """Cleanup."""
        self.stop_camera()
