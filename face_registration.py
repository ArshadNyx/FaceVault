"""
Face Registration Module
This module handles capturing and storing user facial embeddings for
registration (YuNet + SFace, see face_engine.py).
"""

import cv2
import numpy as np
from collections import Counter
from typing import Optional, Tuple, List
from datetime import datetime
from secure_storage import get_storage
import face_engine
from face_engine import get_engine


class FaceRegistration:
    """
    Face registration. A user is enrolled from several quality-checked
    samples so that matching tolerates normal pose and lighting variation.
    """
    
    # Good samples required when a burst of frames is supplied
    MIN_SAMPLES = 3
    MAX_SAMPLES = 8
    
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
        self.engine = get_engine()
        
        print("Face registration module initialized")
    
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
        Detect faces in a frame.
        
        Args:
            frame: Input frame to process
            
        Returns:
            List of face bounding boxes (x, y, width, height), largest first
        """
        return [f.box for f in self.engine.detect(frame)]
    
    def register_user(self, username: str, frames: List[np.ndarray],
                      threshold: float = face_engine.DEFAULT_THRESHOLD) -> Tuple[bool, str]:
        """
        Register a user from one or more frames of their face.
        
        Args:
            username: Username to register
            frames: Frames containing the face (a short burst works best)
            threshold: Match threshold used for consistency and duplicate checks
            
        Returns:
            Tuple of (success, message)
        """
        templates = face_engine.load_templates(self.storage)
        # A user left over with an outdated template may be re-registered in place
        if username in templates:
            return False, f"User '{username}' already exists."
        if not frames:
            return False, "No image provided."
        
        encodings = []
        issues = Counter()
        for frame in frames[:self.MAX_SAMPLES]:
            faces = self.engine.detect(frame)
            if len(faces) == 0:
                issues["No face detected. Please try again."] += 1
                continue
            if len(faces) > 1:
                issues["Multiple faces detected. Please ensure only your face is visible."] += 1
                continue
            encoding, issue = self.engine.analyze(frame, faces[0], enrolling=True)
            if encoding is None:
                issues[issue] += 1
                continue
            encodings.append(encoding)
        
        required = min(self.MIN_SAMPLES, len(frames))
        if len(encodings) < required:
            return False, issues.most_common(1)[0][0]
        
        template = np.stack(encodings)
        # Every sample must be the same person
        if float((template @ template.T).min()) < threshold:
            return False, "Captured samples don't match each other. Please capture again."
        
        # The same face must not unlock two accounts
        for encoding in encodings:
            other, score, _ = face_engine.best_match(encoding, templates)
            if other and score >= threshold:
                return False, f"This face is already registered as '{other}'."
        
        metadata = {
            'registration_date': datetime.now().isoformat(),
            'num_samples': len(encodings)
        }
        
        if self.storage.save_encoding(username, template, metadata):
            return True, f"User '{username}' registered successfully!"
        else:
            return False, "Failed to save user data."
    
    def register_user_single_frame(self, username: str, frame: np.ndarray) -> Tuple[bool, str]:
        """
        Register a user from a single frame (for GUI use).
        
        Args:
            username: Username to register
            frame: Frame containing the face
            
        Returns:
            Tuple of (success, message)
        """
        return self.register_user(username, [frame])
    
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
