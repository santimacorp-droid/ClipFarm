"""
Encryption utility
Use to encrypt sensitive information such ascookies
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

# Retrieving encrypted key
def get_encryption_key():
    """Retrieving encrypted key"""
    # Retrieving key from environment variables; otherwise generating one
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        # Generating a new key
        key = Fernet.generate_key()
        logger.warning("ENCRYPTION_KEYThe environment variable is not set; using temporary credentials. Set the environment variable to keep your data secure.. ")
    
    if isinstance(key, str):
        key = key.encode()
    
    return key

def encrypt_data(data: str) -> str:
    """Encrypting data"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        raise

def decrypt_data(encrypted_data: str) -> str:
    """Decrypting data"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decoded_data = base64.b64decode(encrypted_data.encode())
        decrypted_data = f.decrypt(decoded_data)
        return decrypted_data.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        raise

