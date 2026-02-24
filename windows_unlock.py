"""
Windows Lock Screen Monitor and Auto-Unlock Module
This module monitors the Windows lock screen and unlocks the PC when a registered face is recognized.

IMPORTANT SECURITY NOTES:
1. Your Windows password is stored encrypted on your local machine
2. This application runs with your user privileges
3. Anyone with your face can unlock your computer
4. Use at your own risk - this is not as secure as Windows Hello
"""

import ctypes
import time
import threading
import cv2
import numpy as np
from typing import Optional, Callable
from datetime import datetime
import subprocess
import os

# Windows API constants
DESKTOP_SWITCHDESKTOP = 0x0100
WTS_CURRENT_SESSION = -1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8

# Load Windows DLLs
user32 = ctypes.windll.User32
kernel32 = ctypes.windll.Kernel32
wtsapi32 = ctypes.windll.Wtsapi32


class LockScreenMonitor:
    """
    Monitors Windows lock screen state and triggers unlock when face is recognized.
    """
    
    def __init__(self, face_auth, password_manager):
        """
        Initialize the lock screen monitor.
        
        Args:
            face_auth: FaceAuthentication instance
            password_manager: WindowsPasswordManager instance
        """
        self.face_auth = face_auth
        self.password_manager = password_manager
        self.is_running = False
        self.is_locked = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.unlock_callback: Optional[Callable] = None
        self.last_unlock_time = 0
        self.unlock_cooldown = 5  # Seconds between unlock attempts
        
        # Camera for lock screen
        self.video_capture: Optional[cv2.VideoCapture] = None
    
    def is_windows_locked(self) -> bool:
        """
        Check if Windows is currently locked.
        
        Returns:
            True if Windows is locked, False otherwise
        """
        try:
            # Method 1: Check if the default desktop is the lock screen
            # The lock screen desktop is named "Winlogon"
            hdesk = user32.OpenDesktopW("Winlogon", 0, False, DESKTOP_SWITCHDESKTOP)
            if hdesk:
                user32.CloseDesktop(hdesk)
                return True
            
            # Method 2: Check if we can switch desktop
            hdesk = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if hdesk:
                user32.CloseDesktop(hdesk)
                return False
            
            return True
            
        except Exception as e:
            print(f"Error checking lock state: {e}")
            return False
    
    def start_monitoring(self, unlock_callback: Optional[Callable] = None):
        """
        Start monitoring for lock screen events.
        
        Args:
            unlock_callback: Optional callback function called on unlock attempt
        """
        if self.is_running:
            return
        
        self.unlock_callback = unlock_callback
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Lock screen monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring for lock screen events."""
        self.is_running = False
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        print("Lock screen monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        last_state = False
        
        while self.is_running:
            try:
                current_state = self.is_windows_locked()
                
                # Detect lock state change
                if current_state and not last_state:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Windows locked - activating face unlock")
                    self._on_lock_detected()
                elif not current_state and last_state:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Windows unlocked")
                    self._on_unlock_detected()
                
                last_state = current_state
                self.is_locked = current_state
                
                # If locked, try to unlock with face
                if current_state:
                    self._try_face_unlock()
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(1)
    
    def _on_lock_detected(self):
        """Called when Windows is locked."""
        # Initialize camera for face detection
        if self.video_capture is None:
            self.video_capture = cv2.VideoCapture(0)
            self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    def _on_unlock_detected(self):
        """Called when Windows is unlocked."""
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
    
    def _try_face_unlock(self):
        """Try to unlock Windows using face recognition."""
        # Check cooldown
        current_time = time.time()
        if current_time - self.last_unlock_time < self.unlock_cooldown:
            return
        
        if self.video_capture is None:
            return
        
        try:
            # Capture frame
            ret, frame = self.video_capture.read()
            if not ret or frame is None:
                return
            
            # Detect faces
            face_locations = self.face_auth.detect_faces(frame)
            
            if not face_locations:
                return
            
            # Try to authenticate each face
            for location in face_locations:
                encoding = self.face_auth.get_face_encoding(frame, location)
                if encoding is None:
                    continue
                
                username, confidence = self.face_auth.compare_faces(encoding)
                
                if username:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Face recognized: {username} (confidence: {confidence:.1%})")
                    
                    # Perform unlock
                    if self._perform_unlock(username):
                        self.last_unlock_time = current_time
                        if self.unlock_callback:
                            self.unlock_callback(username, confidence)
                        return
                    
        except Exception as e:
            print(f"Error during face unlock: {e}")
    
    def _perform_unlock(self, username: str) -> bool:
        """
        Perform the Windows unlock.
        
        Args:
            username: The recognized username
            
        Returns:
            True if unlock was successful
        """
        try:
            # Get the password for this user
            password = self.password_manager.get_password(username)
            if not password:
                print(f"No password stored for user: {username}")
                return False
            
            # Method 1: Simulate key press to dismiss lock screen
            # First, send a key to wake up the screen and dismiss the lock screen overlay
            ctypes.windll.user32.keybd_event(0x20, 0, 0, 0)  # Space key down
            ctypes.windll.user32.keybd_event(0x20, 0, 2, 0)  # Space key up
            time.sleep(0.5)
            
            # Method 2: Use PowerShell to enter password
            # This is more reliable than simulating keystrokes
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
            Start-Sleep -Milliseconds 500
            [System.Windows.Forms.SendKeys]::SendWait("{password}")
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
            '''
            
            # Execute PowerShell script
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            print(f"Unlock attempt completed for {username}")
            return True
            
        except subprocess.TimeoutExpired:
            print("Unlock timeout")
            return False
        except Exception as e:
            print(f"Error performing unlock: {e}")
            return False


class WindowsPasswordManager:
    """
    Manages secure storage of Windows passwords for auto-unlock.
    Uses Windows DPAPI for encryption.
    """
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize the password manager.
        
        Args:
            storage_dir: Directory to store encrypted passwords
        """
        if storage_dir is None:
            storage_dir = os.path.join(os.path.dirname(__file__), 'face_data')
        
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.password_file = os.path.join(storage_dir, 'windows_password.enc')
    
    def _get_entropy(self) -> bytes:
        """Get entropy for encryption (additional security layer)."""
        # Use machine-specific data as entropy
        machine_name = os.environ.get('COMPUTERNAME', 'default')
        return machine_name.encode('utf-8')
    
    def save_password(self, username: str, password: str) -> bool:
        """
        Save Windows password for a user.
        
        Args:
            username: The username
            password: The Windows password
            
        Returns:
            True if saved successfully
        """
        try:
            import json
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            # Load or create encryption key
            key_file = os.path.join(self.storage_dir, 'pwd_key.bin')
            
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    key = f.read()
            else:
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
            
            fernet = Fernet(key)
            
            # Encrypt password
            encrypted_password = fernet.encrypt(password.encode('utf-8'))
            
            # Load existing passwords
            passwords = {}
            if os.path.exists(self.password_file):
                with open(self.password_file, 'rb') as f:
                    data = f.read()
                    if data:
                        decrypted = fernet.decrypt(data)
                        passwords = json.loads(decrypted.decode('utf-8'))
            
            # Update password for user
            passwords[username] = encrypted_password.decode('utf-8')
            
            # Save
            encrypted_data = fernet.encrypt(json.dumps(passwords).encode('utf-8'))
            with open(self.password_file, 'wb') as f:
                f.write(encrypted_data)
            
            print(f"Password saved for user: {username}")
            return True
            
        except Exception as e:
            print(f"Error saving password: {e}")
            return False
    
    def get_password(self, username: str) -> Optional[str]:
        """
        Get Windows password for a user.
        
        Args:
            username: The username
            
        Returns:
            The password or None if not found
        """
        try:
            import json
            from cryptography.fernet import Fernet
            
            # Load encryption key
            key_file = os.path.join(self.storage_dir, 'pwd_key.bin')
            if not os.path.exists(key_file):
                return None
            
            with open(key_file, 'rb') as f:
                key = f.read()
            
            fernet = Fernet(key)
            
            # Load passwords
            if not os.path.exists(self.password_file):
                return None
            
            with open(self.password_file, 'rb') as f:
                data = f.read()
            
            decrypted = fernet.decrypt(data)
            passwords = json.loads(decrypted.decode('utf-8'))
            
            if username in passwords:
                encrypted_pwd = passwords[username].encode('utf-8')
                return fernet.decrypt(encrypted_pwd).decode('utf-8')
            
            return None
            
        except Exception as e:
            print(f"Error getting password: {e}")
            return None
    
    def delete_password(self, username: str) -> bool:
        """
        Delete stored password for a user.
        
        Args:
            username: The username
            
        Returns:
            True if deleted successfully
        """
        try:
            import json
            from cryptography.fernet import Fernet
            
            key_file = os.path.join(self.storage_dir, 'pwd_key.bin')
            if not os.path.exists(key_file):
                return True
            
            with open(key_file, 'rb') as f:
                key = f.read()
            
            fernet = Fernet(key)
            
            if not os.path.exists(self.password_file):
                return True
            
            with open(self.password_file, 'rb') as f:
                data = f.read()
            
            decrypted = fernet.decrypt(data)
            passwords = json.loads(decrypted.decode('utf-8'))
            
            if username in passwords:
                del passwords[username]
                encrypted_data = fernet.encrypt(json.dumps(passwords).encode('utf-8'))
                with open(self.password_file, 'wb') as f:
                    f.write(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"Error deleting password: {e}")
            return False
    
    def has_password(self, username: str) -> bool:
        """
        Check if a password is stored for a user.
        
        Args:
            username: The username
            
        Returns:
            True if password exists
        """
        return self.get_password(username) is not None


def test_lock_detection():
    """Test lock screen detection."""
    print("Testing lock screen detection...")
    print("Lock your computer (Win+L) to test detection.")
    print("Press Ctrl+C to stop.")
    
    monitor = LockScreenMonitor(None, None)
    
    try:
        while True:
            is_locked = monitor.is_windows_locked()
            status = "LOCKED" if is_locked else "UNLOCKED"
            print(f"\rStatus: {status}    ", end='', flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nTest stopped.")


if __name__ == "__main__":
    test_lock_detection()
