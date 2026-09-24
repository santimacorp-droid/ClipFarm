"""
APIKey management system - Provides secure key storage, validation, and rotation functionality
"""
import os
import json
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from .error_handler import ConfigurationError, APIError, ValidationError

logger = logging.getLogger(__name__)

class APIKeyManager:
    """APIKey manager"""
    
    def __init__(self, storage_path: Optional[Path] = None, master_password: Optional[str] = None):
        """
        Initialize API key manager
        
        Args:
            storage_path: Key storage path
            master_password: Master password for encryption storage
        """
        self.storage_path = storage_path or Path.home() / ".auto_clips" / "api_keys"
        self.master_password = master_password or self._get_master_password()
        self.fernet = self._create_fernet()
        self.keys_file = self.storage_path / "keys.enc"
        self.metadata_file = self.storage_path / "metadata.json"
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing key
        self._load_keys()
    
    def _get_master_password(self) -> str:
        """Retrieve master password"""
        # Prefer to obtain from environment variables
        master_password = os.getenv("CLIPFARM_MASTER_PASSWORD") or os.getenv("AUTO_CLIPS_MASTER_PASSWORD")
        if master_password:
            return master_password
        
        # Default key for desktop and development environments
        return "clipfarm_default_master_password"
    
    def _create_fernet(self) -> Fernet:
        """Create Fernet cipher"""
        # Generating key from master password
        salt = b'auto_clips_salt'  # In practice, use randomnesssalt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
        return Fernet(key)
    
    def _load_keys(self):
        """Loading stored keys"""
        self.keys: Dict[str, Dict[str, Any]] = {}
        
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'rb') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.fernet.decrypt(encrypted_data)
                    self.keys = json.loads(decrypted_data.decode())
                logger.info(f"Successfully loaded {len(self.keys)} API keys")
            except Exception as e:
                logger.warning(f"Failed to load API key: {e}")
                self.keys = {}
        
        # Loading metadata
        self.metadata: Dict[str, Any] = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load API key metadata: {e}")
                self.metadata = {}
    
    def _save_keys(self):
        """Saving key to file"""
        try:
            # Encrypt and save key
            data = json.dumps(self.keys, ensure_ascii=False)
            encrypted_data = self.fernet.encrypt(data.encode())
            
            with open(self.keys_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Save metadata (unencrypted)
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            logger.debug("APIKey saved")
        except Exception as e:
            logger.error(f"Failed to save API key: {e}")
            raise ConfigurationError(f"Failed to save API key: {e}")
    
    def add_api_key(self, key_name: str, api_key: str, provider: str = "dashscope", 
                   description: str = "", expires_at: Optional[datetime] = None) -> bool:
        """
        Add API key
        
        Args:
            key_name: Key name
            api_key: APIKey value
            provider: Provider (e.g.dashscope)
            description: Description information
            expires_at: Expiration time
            
        Returns:
            Indicates whether addition was successful
        """
        try:
            # Validate key format
            if not self._validate_api_key_format(api_key, provider):
                raise ValidationError(f"Invalid{provider} APIKey format")
            
            # Checking if key already exists
            if key_name in self.keys:
                logger.warning(f"Key name '{key_name}' Already exists, will be overwritten")
            
            # Store key information
            self.keys[key_name] = {
                "api_key": api_key,
                "provider": provider,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "last_used": None,
                "usage_count": 0,
                "is_active": True
            }
            
            # Updating metadata
            self.metadata["last_updated"] = datetime.now().isoformat()
            self.metadata["total_keys"] = len(self.keys)
            
            # Save to file
            self._save_keys()
            
            logger.info(f"Successfully added API key: {key_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add API key: {e}")
            raise
    
    def get_api_key(self, key_name: str) -> Optional[str]:
        """
        Getting API key
        
        Args:
            key_name: Key name
            
        Returns:
            APIKey value; returns None or expired keyNone
        """
        if key_name not in self.keys:
            return None
        
        key_info = self.keys[key_name]
        
        # Check activation status
        if not key_info.get("is_active", True):
            logger.warning(f"APIKey '{key_name}' Disabled")
            return None
        
        # Check expiration status
        if key_info.get("expires_at"):
            expires_at = datetime.fromisoformat(key_info["expires_at"])
            if datetime.now() > expires_at:
                logger.warning(f"APIKey '{key_name}' Expired")
                return None
        
        # Update usage statistics
        key_info["last_used"] = datetime.now().isoformat()
        key_info["usage_count"] = key_info.get("usage_count", 0) + 1
        self._save_keys()
        
        return key_info["api_key"]
    
    def get_active_api_key(self, provider: str = "dashscope") -> Optional[str]:
        """
        Get active API key
        
        Args:
            provider: Provider
            
        Returns:
            Active API key; returns None if none existsNone
        """
        active_keys = []
        
        for key_name, key_info in self.keys.items():
            if (key_info.get("provider") == provider and 
                key_info.get("is_active", True)):
                
                # Check expiration status
                if key_info.get("expires_at"):
                    expires_at = datetime.fromisoformat(key_info["expires_at"])
                    if datetime.now() > expires_at:
                        continue
                
                active_keys.append((key_name, key_info))
        
        if not active_keys:
            return None
        
        # Returns most recently used key first
        active_keys.sort(key=lambda x: x[1].get("last_used", ""), reverse=True)
        return active_keys[0][1]["api_key"]
    
    def remove_api_key(self, key_name: str) -> bool:
        """
        Deleting API key
        
        Args:
            key_name: Key name
            
        Returns:
            Indicates whether deletion was successful
        """
        if key_name not in self.keys:
            logger.warning(f"APIKey '{key_name}' Does not exist")
            return False
        
        del self.keys[key_name]
        self.metadata["last_updated"] = datetime.now().isoformat()
        self.metadata["total_keys"] = len(self.keys)
        self._save_keys()
        
        logger.info(f"Successfully deleted API key: {key_name}")
        return True
    
    def update_api_key(self, key_name: str, **updates) -> bool:
        """
        Updating API key information
        
        Args:
            key_name: Key name
            **updates: Field to be updated
            
        Returns:
            Indicates whether update was successful
        """
        if key_name not in self.keys:
            logger.warning(f"APIKey '{key_name}' Does not exist")
            return False
        
        # Fields allowed for update
        allowed_fields = ["description", "expires_at", "is_active"]
        
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "expires_at" and value is not None:
                    if isinstance(value, datetime):
                        value = value.isoformat()
                self.keys[key_name][field] = value
        
        self.metadata["last_updated"] = datetime.now().isoformat()
        self._save_keys()
        
        logger.info(f"Successfully updated API key: {key_name}")
        return True
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        """
        List all API keys (key values are omitted))
        
        Returns:
            APIList of key information
        """
        result = []
        
        for key_name, key_info in self.keys.items():
            # Does not return actual API key value
            safe_info = {
                "name": key_name,
                "provider": key_info.get("provider"),
                "description": key_info.get("description"),
                "created_at": key_info.get("created_at"),
                "expires_at": key_info.get("expires_at"),
                "last_used": key_info.get("last_used"),
                "usage_count": key_info.get("usage_count", 0),
                "is_active": key_info.get("is_active", True)
            }
            
            # Check expiration status
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                safe_info["is_expired"] = datetime.now() > expires_at
            else:
                safe_info["is_expired"] = False
            
            result.append(safe_info)
        
        return result
    
    def test_api_key(self, key_name: str) -> Dict[str, Any]:
        """
        Testing API key
        
        Args:
            key_name: Key name
            
        Returns:
            Test results
        """
        api_key = self.get_api_key(key_name)
        if not api_key:
            return {
                "success": False,
                "error": "Key does not exist or has expired"
            }
        
        try:
            # Here you can add actual API test logic
            # Currently just basic format validation
            if self._validate_api_key_format(api_key, "dashscope"):
                return {
                    "success": True,
                    "message": "APIKey format is correct"
                }
            else:
                return {
                    "success": False,
                    "error": "APIKey format is invalid"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Tests failed: {str(e)}"
            }
    
    def _validate_api_key_format(self, api_key: str, provider: str) -> bool:
        """
        Validating API key format
        
        Args:
            api_key: APIKey
            provider: Provider
            
        Returns:
            Is the format correct?
        """
        if not api_key or len(api_key.strip()) < 10:
            return False
        
        if provider == "dashscope":
            # DashScope API key is typically a string starting with `sk-`
            return api_key.startswith("sk-") and len(api_key) >= 20
        
        # Other providers can add corresponding validation logic
        return True
    
    def rotate_api_key(self, key_name: str, new_api_key: str) -> bool:
        """
        Rotating API key
        
        Args:
            key_name: Key name
            new_api_key: New API key
            
        Returns:
            Rotation status
        """
        if key_name not in self.keys:
            logger.warning(f"APIKey '{key_name}' Does not exist")
            return False
        
        old_key_info = self.keys[key_name]
        
        # Validating new key format
        if not self._validate_api_key_format(new_api_key, old_key_info.get("provider", "dashscope")):
            raise ValidationError("Invalid new API key format")
        
        # Update key
        self.keys[key_name]["api_key"] = new_api_key
        self.keys[key_name]["rotated_at"] = datetime.now().isoformat()
        self.keys[key_name]["last_used"] = None
        self.keys[key_name]["usage_count"] = 0
        
        self.metadata["last_updated"] = datetime.now().isoformat()
        self._save_keys()
        
        logger.info(f"Successfully rotated API key: {key_name}")
        return True
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Retrieve usage statistics
        
        Returns:
            Usage statistics
        """
        total_keys = len(self.keys)
        active_keys = sum(1 for k in self.keys.values() if k.get("is_active", True))
        expired_keys = 0
        total_usage = 0
        
        for key_info in self.keys.values():
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                if datetime.now() > expires_at:
                    expired_keys += 1
            
            total_usage += key_info.get("usage_count", 0)
        
        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "total_usage": total_usage,
            "last_updated": self.metadata.get("last_updated")
        }
    
    def cleanup_expired_keys(self) -> int:
        """
        Purge expired API keys
        
        Returns:
            Number of keys cleaned up
        """
        cleaned_count = 0
        current_time = datetime.now()
        
        keys_to_remove = []
        
        for key_name, key_info in self.keys.items():
            if key_info.get("expires_at"):
                expires_at = datetime.fromisoformat(key_info["expires_at"])
                if current_time > expires_at:
                    keys_to_remove.append(key_name)
        
        for key_name in keys_to_remove:
            self.remove_api_key(key_name)
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} an expired API key")
        
        return cleaned_count

# Global API key manager instance
api_key_manager = APIKeyManager()

def get_api_key(key_name: Optional[str] = None, provider: str = "dashscope") -> Optional[str]:
    """
    Utility function to get API key
    
    Args:
        key_name: Key name; if None, retrieve active key
        provider: Provider
        
    Returns:
        APIKey
    """
    if key_name:
        return api_key_manager.get_api_key(key_name)
    else:
        return api_key_manager.get_active_api_key(provider)

def set_api_key(api_key: str, key_name: str = "default", provider: str = "dashscope") -> bool:
    """
    Utility function to set API key
    
    Args:
        api_key: APIKey
        key_name: Key name
        provider: Provider
        
    Returns:
        Indicates whether setting was successful
    """
    return api_key_manager.add_api_key(key_name, api_key, provider) 