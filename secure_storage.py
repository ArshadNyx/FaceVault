"""
Secure Storage Utility for Facial Encodings
This module handles secure storage and retrieval of facial encoding data
using encryption to protect sensitive biometric data.
"""

import os
import json
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional, Dict, Any
import numpy as np


class SecureStorage:
    """
    A class to securely store and retrieve facial encoding data.
    Uses Fernet symmetric encryption for data protection.
    """
    
    def __init__(self, storage_dir: str = "face_data", password: str = "default_key"):
        """
        Initialize the secure storage.
        
        Args:
            storage_dir: Directory to store encrypted data
            password: Password used to derive encryption key
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.storage_dir / "encodings.enc"
        self.key_file = self.storage_dir / "key.bin"
        self.salt_file = self.storage_dir / "salt.bin"
        
        # Initialize or load encryption key
        self._init_encryption(password)
    
    def _init_encryption(self, password: str) -> None:
        """
        Initialize encryption key from password or generate new one.
        
        Args:
            password: Password for key derivation
        """
        if self.salt_file.exists():
            # Load existing salt
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
        else:
            # Generate new salt
            salt = os.urandom(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
        
        # Derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)
    
    def _encode_numpy(self, arr: np.ndarray) -> str:
        """
        Convert numpy array to JSON-serializable string.
        
        Args:
            arr: Numpy array to encode
            
        Returns:
            Base64 encoded string representation
        """
        return base64.b64encode(arr.tobytes()).decode('utf-8')
    
    def _decode_numpy(self, encoded: str, shape: tuple = (128,)) -> np.ndarray:
        """
        Convert encoded string back to numpy array.
        
        Args:
            encoded: Base64 encoded string
            shape: Shape of the original array
            
        Returns:
            Numpy array
        """
        data = base64.b64decode(encoded.encode('utf-8'))
        return np.frombuffer(data, dtype=np.float64).reshape(shape)
    
    def save_encoding(self, username: str, encoding: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a user's facial encoding securely.
        
        Args:
            username: Username to associate with encoding
            encoding: Facial encoding array (128-dimensional)
            metadata: Optional additional metadata
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            # Load existing data
            data = self._load_all_data()
            
            # Prepare user data
            user_data = {
                'encoding': self._encode_numpy(encoding),
                'encoding_shape': encoding.shape,
                'metadata': metadata or {}
            }
            
            # Update data
            data[username] = user_data
            
            # Encrypt and save
            json_data = json.dumps(data)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            with open(self.data_file, 'wb') as f:
                f.write(encrypted_data)
            
            return True
        except Exception as e:
            print(f"Error saving encoding: {e}")
            return False
    
    def load_encoding(self, username: str) -> Optional[np.ndarray]:
        """
        Load a user's facial encoding.
        
        Args:
            username: Username to look up
            
        Returns:
            Facial encoding array if found, None otherwise
        """
        try:
            data = self._load_all_data()
            
            if username not in data:
                return None
            
            user_data = data[username]
            encoding = self._decode_numpy(
                user_data['encoding'],
                tuple(user_data['encoding_shape'])
            )
            
            return encoding
        except Exception as e:
            print(f"Error loading encoding: {e}")
            return None
    
    def load_user_metadata(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Load metadata for a user.
        
        Args:
            username: Username to look up
            
        Returns:
            Metadata dictionary if found, None otherwise
        """
        try:
            data = self._load_all_data()
            
            if username not in data:
                return None
            
            return data[username].get('metadata', {})
        except Exception as e:
            print(f"Error loading metadata: {e}")
            return None
    
    def _load_all_data(self) -> Dict[str, Any]:
        """
        Load and decrypt all stored data.
        
        Returns:
            Dictionary of all user data
        """
        if not self.data_file.exists():
            return {}
        
        try:
            with open(self.data_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Error loading data: {e}")
            return {}
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user's encoding data.
        
        Args:
            username: Username to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            data = self._load_all_data()
            
            if username not in data:
                return False
            
            del data[username]
            
            # Encrypt and save
            json_data = json.dumps(data)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            with open(self.data_file, 'wb') as f:
                f.write(encrypted_data)
            
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False
    
    def list_users(self) -> list:
        """
        List all registered usernames.
        
        Returns:
            List of registered usernames
        """
        data = self._load_all_data()
        return list(data.keys())
    
    def user_exists(self, username: str) -> bool:
        """
        Check if a user is registered.
        
        Args:
            username: Username to check
            
        Returns:
            True if user exists, False otherwise
        """
        data = self._load_all_data()
        return username in data


# Singleton instance for easy access
_storage_instance: Optional[SecureStorage] = None


def get_storage(storage_dir: str = "face_data", password: str = "default_key") -> SecureStorage:
    """
    Get or create the singleton storage instance.
    
    Args:
        storage_dir: Directory for storage
        password: Password for encryption
        
    Returns:
        SecureStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = SecureStorage(storage_dir, password)
    return _storage_instance