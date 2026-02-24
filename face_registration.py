"""
Face Registration Module - Optimized for Real-Time Performance
This module handles capturing and storing user facial encodings for registration.
Optimized for high FPS and smooth video display.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from datetime import datetime
from secure_storage import get_storage
import os


class FaceRegistration:
    """
    Optimized face registration for real-time performance.
    Uses lightweight detection for smooth video display.
    """
    
    def __init__(self, camera_index: int = 0):
        """
        Initialize the face registration module.
        
        Args:
            camera_index: Index of the camera to use (default: 0)
        """
        self.camera_index = camera_index
        self.video_capture: Optional[cv2.VideoCapture] = None
        self.storage = get_storage()
        self.is_running = False
        
        # Optimized face size (smaller = faster)
        self.face_size = (64, 64)
        
        # Frame skipping for performance
        self.frame_count = 0
        self.detect_every_n_frames = 2
        self.cached_face_locations = []
        
        # Initialize face detector
        self._init_face_detector()
        
        print("Face registration module initialized (optimized mode)")
    
    def _init_face_detector(self):
        """Initialize optimized face detector."""
        try:
            # Try YuNet first (fastest)
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
            # Fallback to Haar Cascade
            print(f"YuNet not available, using Haar Cascade: {e}")
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.use_haar = True
            self.use_yunet = False
        
        self.use_dnn = False
    
    def start_camera(self) -> bool:
        """
        Start the video capture with optimized settings.
        
        Returns:
            True if camera started successfully, False otherwise
        """
        try:
            self.video_capture = cv2.VideoCapture(self.camera_index)
            if not self.video_capture.isOpened():
                print("Error: Could not open camera")
                return False
            
            # Optimized camera settings for high FPS
            self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video_capture.set(cv2.CAP_PROP_FPS, 30)
            self.video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer
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
        """
        Capture a single frame from the camera.
        
        Returns:
            Captured frame as numpy array, or None if capture failed
        """
        if self.video_capture is None or not self.is_running:
            return None
        
        ret, frame = self.video_capture.read()
        if not ret:
            return None
        
        return frame
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect faces with frame skipping for performance.
        
        Args:
            frame: Input frame to process
            
        Returns:
            List of face bounding boxes (x, y, width, height)
        """
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
                if fw >= 50 and fh >= 50:
                    result.append((x, y, fw, fh))
        
        return result
    
    def _detect_haar_fast(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Optimized Haar Cascade detection."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=4,
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        return [tuple(f) for f in faces]
    
    def get_face_encoding(self, frame: np.ndarray, face_location: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """
        Get facial encoding for a specific face location.
        
        Args:
            frame: Input frame
            face_location: Location of the face (x, y, width, height)
            
        Returns:
            Face encoding array, or None if encoding failed
        """
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
            
            # Simple histogram equalization
            equalized = cv2.equalizeHist(resized)
            
            # Flatten and normalize
            encoding = equalized.flatten().astype(np.float64)
            encoding = (encoding - encoding.mean()) / (encoding.std() + 1e-8)
            
            return encoding
            
        except Exception as e:
            print(f"Error getting face encoding: {e}")
            return None
    
    def register_user_single_frame(self, username: str, frame: np.ndarray) -> Tuple[bool, str]:
        """
        Register a user from a single frame (for GUI use).
        
        Args:
            username: Username to register
            frame: Frame containing the face
            
        Returns:
            Tuple of (success, message)
        """
        if self.storage.user_exists(username):
            return False, f"User '{username}' already exists."
        
        face_locations = self.detect_faces(frame)
        
        if len(face_locations) == 0:
            return False, "No face detected. Please try again."
        
        if len(face_locations) > 1:
            return False, "Multiple faces detected. Please ensure only your face is visible."
        
        encoding = self.get_face_encoding(frame, face_locations[0])
        
        if encoding is None:
            return False, "Failed to generate face encoding. Please try again."
        
        metadata = {
            'registration_date': datetime.now().isoformat(),
            'num_samples': 1
        }
        
        if self.storage.save_encoding(username, encoding, metadata):
            return True, f"User '{username}' registered successfully!"
        else:
            return False, "Failed to save user data."
    
    def get_registered_users(self) -> List[str]:
        """
        Get list of all registered users.
        
        Returns:
            List of registered usernames
        """
        return self.storage.list_users()
    
    def delete_user(self, username: str) -> Tuple[bool, str]:
        """
        Delete a registered user.
        
        Args:
            username: Username to delete
            
        Returns:
            Tuple of (success, message)
        """
        if not self.storage.user_exists(username):
            return False, f"User '{username}' not found."
        
        if self.storage.delete_user(username):
            return True, f"User '{username}' deleted successfully."
        else:
            return False, f"Failed to delete user '{username}'."
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.stop_camera()
