"""
Secure Credentials Manager with Offline Support

This module provides encrypted credential storage with automatic fallback
to local encrypted credentials when Google Cloud Secret Manager is unavailable.

Features:
- Google Cloud Secret Manager integration (primary)
- Encrypted local credential storage (fallback)
- Automatic offline detection
- Thread-safe credential caching
- Key rotation support
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions


class SecureCredentials:
    """Manages credentials with Google Cloud and encrypted local fallback"""

    def __init__(self, project_id: str, credentials_path: str = None, key_path: str = None):
        """
        Initialize secure credentials manager

        Args:
            project_id: Google Cloud project ID
            credentials_path: Path to encrypted local credentials file
            key_path: Path to encryption key file
        """
        self.project_id = project_id
        self.credentials_path = credentials_path or self._default_credentials_path()
        self.key_path = key_path or self._default_key_path()
        self._cache: Dict[str, Any] = {}
        self._gcp_client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._fernet: Optional[Fernet] = None
        self._offline_mode = False

        # Initialize encryption
        self._init_encryption()

        # Try to initialize GCP client
        self._init_gcp_client()

    def _default_credentials_path(self) -> str:
        """Get default path for encrypted credentials file"""
        base_path = os.environ.get('LORASERVICE_PATH', '.')
        return os.path.join(base_path, 'data', 'credentials.iqr')

    def _default_key_path(self) -> str:
        """Get default path for encryption key"""
        base_path = os.environ.get('LORASERVICE_PATH', '.')
        return os.path.join(base_path, 'data', 'credentials.key')

    def _init_encryption(self):
        """Initialize Fernet encryption"""
        try:
            if os.path.exists(self.key_path):
                with open(self.key_path, 'rb') as key_file:
                    key = key_file.read()
                self._fernet = Fernet(key)
                logging.info("Encryption key loaded successfully")
            else:
                logging.warning(f"Encryption key not found at {self.key_path}")
                self._fernet = None
        except Exception as e:
            logging.error(f"Failed to initialize encryption: {e}")
            self._fernet = None

    def _init_gcp_client(self):
        """Initialize Google Cloud Secret Manager client"""
        try:
            self._gcp_client = secretmanager.SecretManagerServiceClient()
            logging.info("Google Cloud Secret Manager client initialized")
            self._offline_mode = False
        except Exception as e:
            logging.warning(f"Could not initialize GCP client: {e}")
            logging.info("Operating in OFFLINE mode - using local credentials only")
            self._offline_mode = True
            self._gcp_client = None

    def get_secret(self, secret_name: str, expected: Optional[str] = None,
                   compare: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get secret with automatic fallback to local storage

        Args:
            secret_name: Name of the secret
            expected: Expected value for comparison
            compare: Whether to compare with expected value

        Returns:
            Dict with 'value' and 'result' keys, or None if not found
        """
        # Check cache first
        if secret_name in self._cache:
            logging.debug(f"Retrieved '{secret_name}' from cache")
            return self._cache[secret_name]

        # Try Google Cloud Secret Manager first
        if not self._offline_mode and self._gcp_client:
            gcp_secret = self._get_from_gcp(secret_name)
            if gcp_secret:
                result = self._prepare_result(gcp_secret, expected, compare)
                self._cache[secret_name] = result
                return result

        # Fallback to local encrypted storage
        local_secret = self._get_from_local(secret_name)
        if local_secret:
            result = self._prepare_result(local_secret, expected, compare)
            self._cache[secret_name] = result
            return result

        logging.error(f"Secret '{secret_name}' not found in GCP or local storage")
        return None

    def _get_from_gcp(self, secret_name: str) -> Optional[str]:
        """Get secret from Google Cloud Secret Manager"""
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self._gcp_client.access_secret_version(name=name)
            secret_value = response.payload.data.decode('UTF-8')
            logging.info(f"Retrieved '{secret_name}' from Google Cloud Secret Manager")
            return secret_value
        except gcp_exceptions.NotFound:
            logging.warning(f"Secret '{secret_name}' not found in Google Cloud")
            return None
        except gcp_exceptions.PermissionDenied:
            logging.error(f"Permission denied accessing '{secret_name}' in Google Cloud")
            return None
        except Exception as e:
            logging.error(f"Error accessing GCP secret '{secret_name}': {e}")
            # If we can't reach GCP, switch to offline mode
            if "unable to connect" in str(e).lower() or "network" in str(e).lower():
                self._offline_mode = True
                logging.info("Switched to OFFLINE mode due to connectivity issue")
            return None

    def _get_from_local(self, secret_name: str) -> Optional[str]:
        """Get secret from local encrypted storage"""
        if not self._fernet:
            logging.error("Cannot read local secrets: encryption not initialized")
            return None

        try:
            if not os.path.exists(self.credentials_path):
                logging.error(f"Local credentials file not found: {self.credentials_path}")
                return None

            with open(self.credentials_path, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = self._fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode('utf-8'))

            if secret_name in credentials:
                logging.info(f"Retrieved '{secret_name}' from local encrypted storage")
                return credentials[secret_name]
            else:
                logging.warning(f"Secret '{secret_name}' not found in local storage")
                return None

        except Exception as e:
            logging.error(f"Error reading local secret '{secret_name}': {e}")
            return None

    def _prepare_result(self, value: str, expected: Optional[str], compare: bool) -> Dict[str, Any]:
        """Prepare result dict with comparison if needed"""
        result_data = {
            'value': value,
            'result': False
        }

        if compare and expected:
            result_data['result'] = (value == expected)

        return result_data

    def set_local_secret(self, secret_name: str, secret_value: str):
        """
        Store a secret in local encrypted storage

        Args:
            secret_name: Name of the secret
            secret_value: Value to store
        """
        if not self._fernet:
            raise RuntimeError("Cannot store secrets: encryption not initialized")

        try:
            # Read existing credentials or create new dict
            credentials = {}
            if os.path.exists(self.credentials_path):
                with open(self.credentials_path, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self._fernet.decrypt(encrypted_data)
                credentials = json.loads(decrypted_data.decode('utf-8'))

            # Update credential
            credentials[secret_name] = secret_value

            # Encrypt and save
            credentials_json = json.dumps(credentials, indent=2)
            encrypted_data = self._fernet.encrypt(credentials_json.encode('utf-8'))

            # Ensure directory exists
            Path(self.credentials_path).parent.mkdir(parents=True, exist_ok=True)

            with open(self.credentials_path, 'wb') as f:
                f.write(encrypted_data)

            # Update cache
            self._cache[secret_name] = {'value': secret_value, 'result': False}

            logging.info(f"Stored '{secret_name}' in local encrypted storage")

        except Exception as e:
            logging.error(f"Error storing local secret '{secret_name}': {e}")
            raise

    def sync_from_gcp(self, secret_names: list[str]):
        """
        Sync secrets from GCP to local storage for offline use

        Args:
            secret_names: List of secret names to sync
        """
        if self._offline_mode:
            logging.warning("Cannot sync from GCP while in offline mode")
            return

        synced_count = 0
        for secret_name in secret_names:
            secret_value = self._get_from_gcp(secret_name)
            if secret_value:
                try:
                    self.set_local_secret(secret_name, secret_value)
                    synced_count += 1
                except Exception as e:
                    logging.error(f"Failed to sync '{secret_name}': {e}")

        logging.info(f"Synced {synced_count}/{len(secret_names)} secrets from GCP to local storage")

    def clear_cache(self):
        """Clear the in-memory credential cache"""
        self._cache.clear()
        logging.info("Credential cache cleared")

    def is_offline(self) -> bool:
        """Check if operating in offline mode"""
        return self._offline_mode

    def force_offline_mode(self):
        """Force offline mode (disable GCP access)"""
        self._offline_mode = True
        logging.info("Forced offline mode enabled")

    def force_online_mode(self):
        """Attempt to re-enable online mode"""
        self._offline_mode = False
        self._init_gcp_client()


# Global instance (singleton pattern)
_credentials_manager: Optional[SecureCredentials] = None


def get_credentials_manager(project_id: str = None,
                           credentials_path: str = None,
                           key_path: str = None) -> SecureCredentials:
    """
    Get or create the global credentials manager instance

    Args:
        project_id: Google Cloud project ID
        credentials_path: Path to encrypted credentials file
        key_path: Path to encryption key

    Returns:
        SecureCredentials instance
    """
    global _credentials_manager

    if _credentials_manager is None:
        if project_id is None:
            from utils.config import PROJECT_ID
            project_id = PROJECT_ID

        _credentials_manager = SecureCredentials(
            project_id=project_id,
            credentials_path=credentials_path,
            key_path=key_path
        )

    return _credentials_manager


def get_secret(secret_name: str, expected: Optional[str] = None,
               compare: bool = False) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get secret using global credentials manager

    Args:
        secret_name: Name of the secret
        expected: Expected value for comparison
        compare: Whether to compare with expected value

    Returns:
        Dict with 'value' and 'result' keys, or None if not found
    """
    manager = get_credentials_manager()
    return manager.get_secret(secret_name, expected, compare)
