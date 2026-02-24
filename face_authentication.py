"""
Face Authentication Module - Optimized for Real-Time Performance
This module handles face recognition and authentication by comparing
live camera input with stored facial encodings.
Optimized for high FPS and low latency.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
from datetime import datetime
from secure_storage import get_storage
import os


class AuthenticationResult:
    """Class to hold authentication results."""
    
    def __init__(self, success: bool, username: str = "", confidence: float = 0.0, 
                 message: str = "", timestamp: str = "", face_location: Tuple[int, int, int, int] = None):
        self.success = success
        self.username = username
        self.confidence = confidence
        self.message = message
        self.timestamp = timestamp or datetime.now().isoformat()
        self.face_location = face_location
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'username': self.username,
            'confidence': self.confidence,
            'message': self.message,
            'timestamp': self.timestamp,
            'face_location': self.face_location
        }


class FaceAuthentication:
    """
    Optimized face authentication for real-time performance.
    Uses lightweight detection and fast encoding comparison.
    """
    
    DEFAULT_THRESHOLD = 0.5
    
    def __init__(self, camera_index: int = 0, threshold: float = DEFAULT_THRESHOLD):
        self.camera_index = camera_index
        self.threshold = threshold
        self.video_capture: Optional[cv2.VideoCapture] = None
        self.storage = get_storage()
        self.is_running = False
        self.known_encodings: Dict[str, np.ndarray] = {}
        
        # Optimized face size (smaller = faster)
        self.face_size = (64, 64)
        
        # Frame skipping for performance
        self.frame_count = 0
        self.detect_every_n_frames = 2  # Detect faces every 2 frames
        self.cached_face_locations = []
        
        # Initialize face detector
        self._init_face_detector()
        
        # Load known encodings
        self._load_known_encodings()
        
        print("Face authentication module initialized (optimized mode)")
    
    def _init_face_detector(self):
        """Initialize optimized face detector."""
        # Use YuNet if available (fastest), otherwise Haar Cascade
        try:
            # Try to use YuNet (OpenCV's DNN face detector)
            model_path = os.path.join(os.path.dirname(__file__), 'models', 'face_detection_yunet_2023mar.onnx')
            if os.path.exists(model_path):
                self.face_detector = cv2.FaceDetectorYN.create(
                    model_path, "", (640, 480),
                    score_threshold=0.7,
                    nms_threshold=0.3,
                    top_k=5000
                )
                self.use_yunet = True
                self.use_haar = False
                print("Using YuNet face detector (fast)")
            else:
                raise FileNotFoundError("YuNet model not found")
        except Exception as e:
            # Fallback to Haar Cascade (still fast with optimized parameters)
            print(f"YuNet not available, using Haar Cascade: {e}")
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.use_haar = True
            self.use_yunet = False
        
        self.use_dnn = False
    
    def _load_known_encodings(self) -> None:
        """Load all known face encodings from storage."""
        users = self.storage.list_users()
        self.known_encodings = {}
        
        for username in users:
            encoding = self.storage.load_encoding(username)
            if encoding is not None:
                self.known_encodings[username] = encoding
        
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
        """Detect faces with frame skipping for performance."""
        self.frame_count += 1
        
        # Use cached face locations for skipped frames
        if self.frame_count % self.detect_every_n_frames != 0:
            return self.cached_face_locations
        
        # Detect faces on every Nth frame
        if self.use_yunet:
            faces = self._detect_yunet(frame)
        else:
            faces = self._detect_haar_fast(frame)
        
        self.cached_face_locations = faces
        return faces
    
    def _detect_yunet(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Fast face detection using YuNet."""
        h, w = frame.shape[:2]
        self.face_detector.setInputSize((w, h))
        
        _, faces = self.face_detector.detect(frame)
        
        result = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[:4].astype(int)
                # Filter small faces
                if fw >= 50 and fh >= 50:
                    result.append((x, y, fw, fh))
        
        return result
    
    def _detect_haar_fast(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Optimized Haar Cascade detection."""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Fast detection parameters
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,  # Larger scale factor = faster
            minNeighbors=4,   # Fewer neighbors = faster
            minSize=(50, 50),  # Larger min size = faster
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        return [tuple(f) for f in faces]
    
    def get_face_encoding(self, frame: np.ndarray, face_location: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Fast face encoding extraction."""
        try:
            x, y, w, h = face_location
            
            # Minimal padding
            padding = 5
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(frame.shape[1], x + w + padding)
            y2 = min(frame.shape[0], y + h + padding)
            
            face_img = frame[y1:y2, x1:x2]
            
            if face_img.size == 0:
                return None
            
            # Fast preprocessing
            gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray_face, self.face_size, interpolation=cv2.INTER_LINEAR)
            
            # Simple histogram equalization for lighting normalization
            equalized = cv2.equalizeHist(resized)
            
            # Flatten and normalize
            encoding = equalized.flatten().astype(np.float64)
            encoding = (encoding - encoding.mean()) / (encoding.std() + 1e-8)
            
            return encoding
            
        except Exception as e:
            print(f"Error getting face encoding: {e}")
            return None
    
    def calculate_similarity(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """Fast similarity calculation using correlation."""
        if encoding1.shape != encoding2.shape:
            return 0.0
        
        # Fast correlation
        correlation = np.corrcoef(encoding1, encoding2)[0, 1]
        similarity = (correlation + 1) / 2
        
        return max(0.0, min(1.0, similarity))
    
    def calculate_distance(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """Fast distance calculation."""
        if encoding1.shape != encoding2.shape:
            return 1.0
        
        # Normalized Euclidean distance
        diff = encoding1 - encoding2
        distance = np.sqrt(np.sum(diff * diff)) / len(encoding1)
        
        return min(1.0, distance)
    
    def compare_faces(self, encoding: np.ndarray) -> Tuple[Optional[str], float]:
        """Compare face encoding with known encodings."""
        if not self.known_encodings:
            return None, 0.0
        
        best_match = None
        best_similarity = 0.0
        best_distance = float('inf')
        
        for username, known_encoding in self.known_encodings.items():
            if encoding.shape != known_encoding.shape:
                continue
            
            similarity = self.calculate_similarity(encoding, known_encoding)
            distance = self.calculate_distance(encoding, known_encoding)
            
            if distance < best_distance:
                best_distance = distance
                best_similarity = similarity
                best_match = username
        
        if best_distance <= self.threshold:
            return best_match, best_similarity
        
        return None, best_similarity
    
    def authenticate_frame(self, frame: np.ndarray) -> List[AuthenticationResult]:
        """Authenticate all faces in a frame."""
        results = []
        
        face_locations = self.detect_faces(frame)
        
        if not face_locations:
            return [AuthenticationResult(
                success=False,
                message="No face detected",
                confidence=0.0,
                face_location=None
            )]
        
        for location in face_locations:
            x, y, w, h = location
            
            # Skip small faces
            if w < 50 or h < 50:
                continue
            
            encoding = self.get_face_encoding(frame, location)
            
            if encoding is None:
                results.append(AuthenticationResult(
                    success=False,
                    message="Failed to encode",
                    confidence=0.0,
                    face_location=location
                ))
                continue
            
            username, confidence = self.compare_faces(encoding)
            
            if username:
                results.append(AuthenticationResult(
                    success=True,
                    username=username,
                    confidence=confidence,
                    message=f"Access granted for {username}",
                    face_location=location
                ))
            else:
                results.append(AuthenticationResult(
                    success=False,
                    confidence=confidence,
                    message="Access denied",
                    face_location=location
                ))
        
        return results if results else [AuthenticationResult(
            success=False,
            message="No valid face detected",
            confidence=0.0
        )]
    
    def authenticate_single_face(self, frame: np.ndarray) -> AuthenticationResult:
        """Authenticate a single face in the frame."""
        results = self.authenticate_frame(frame)
        
        if not results:
            return AuthenticationResult(
                success=False,
                message="No face detected"
            )
        
        # Return the best result
        successful_results = [r for r in results if r.success]
        if successful_results:
            return max(successful_results, key=lambda r: r.confidence)
        
        return results[0]
    
    def set_threshold(self, threshold: float) -> None:
        """Set the face matching threshold."""
        self.threshold = max(0.0, min(1.0, threshold))
    
    def get_registered_users(self) -> List[str]:
        """Get list of registered users."""
        return list(self.known_encodings.keys())
    
    def __del__(self):
        """Cleanup."""
        self.stop_camera()
