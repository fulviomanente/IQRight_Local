"""
Credential Setup Utility

This script helps initialize and manage encrypted local credentials
for offline operation.

Usage:
    python credential_setup.py --generate-key
    python credential_setup.py --add apiUsername myuser
    python credential_setup.py --add apiPassword mypass
    python credential_setup.py --sync-from-gcp
    python credential_setup.py --list
"""

import argparse
import os
import sys
import json
import getpass
from pathlib import Path
from cryptography.fernet import Fernet


def generate_key(key_path: str):
    """Generate a new encryption key"""
    try:
        # Ensure directory exists
        Path(key_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate key
        key = Fernet.generate_key()

        # Save key
        with open(key_path, 'wb') as key_file:
            key_file.write(key)

        # Set restrictive permissions (owner read/write only)
        os.chmod(key_path, 0o600)

        print(f"✓ Encryption key generated: {key_path}")
        print(f"  IMPORTANT: Keep this key secure and backed up!")
        return True

    except Exception as e:
        print(f"✗ Error generating key: {e}")
        return False


def add_credential(credentials_path: str, key_path: str,
                  secret_name: str, secret_value: str = None):
    """Add or update a credential in local storage"""
    try:
        # Load encryption key
        if not os.path.exists(key_path):
            print(f"✗ Encryption key not found: {key_path}")
            print(f"  Run with --generate-key first")
            return False

        with open(key_path, 'rb') as f:
            key = f.read()
        fernet = Fernet(key)

        # Load existing credentials or create new dict
        credentials = {}
        if os.path.exists(credentials_path):
            with open(credentials_path, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode('utf-8'))

        # Get secret value if not provided
        if secret_value is None:
            secret_value = getpass.getpass(f"Enter value for '{secret_name}': ")

        # Update credential
        credentials[secret_name] = secret_value

        # Encrypt and save
        credentials_json = json.dumps(credentials, indent=2)
        encrypted_data = fernet.encrypt(credentials_json.encode('utf-8'))

        # Ensure directory exists
        Path(credentials_path).parent.mkdir(parents=True, exist_ok=True)

        with open(credentials_path, 'wb') as f:
            f.write(encrypted_data)

        # Set restrictive permissions
        os.chmod(credentials_path, 0o600)

        print(f"✓ Credential '{secret_name}' saved to encrypted storage")
        return True

    except Exception as e:
        print(f"✗ Error adding credential: {e}")
        return False


def list_credentials(credentials_path: str, key_path: str):
    """List all credential names (not values) in local storage"""
    try:
        if not os.path.exists(credentials_path):
            print(f"✗ Credentials file not found: {credentials_path}")
            return False

        if not os.path.exists(key_path):
            print(f"✗ Encryption key not found: {key_path}")
            return False

        with open(key_path, 'rb') as f:
            key = f.read()
        fernet = Fernet(key)

        with open(credentials_path, 'rb') as f:
            encrypted_data = f.read()

        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode('utf-8'))

        print(f"\nStored credentials in {credentials_path}:")
        for secret_name in sorted(credentials.keys()):
            value_preview = credentials[secret_name][:20] + "..." if len(credentials[secret_name]) > 20 else credentials[secret_name]
            print(f"  • {secret_name}: {value_preview}")

        print(f"\nTotal: {len(credentials)} credentials")
        return True

    except Exception as e:
        print(f"✗ Error listing credentials: {e}")
        return False


def sync_from_gcp(credentials_path: str, key_path: str, project_id: str, secrets: list):
    """Sync credentials from Google Cloud Secret Manager"""
    try:
        from google.cloud import secretmanager

        print(f"Syncing secrets from Google Cloud Project: {project_id}")

        # Initialize GCP client
        client = secretmanager.SecretManagerServiceClient()

        # Load encryption key
        if not os.path.exists(key_path):
            print(f"✗ Encryption key not found: {key_path}")
            print(f"  Run with --generate-key first")
            return False

        with open(key_path, 'rb') as f:
            key = f.read()
        fernet = Fernet(key)

        # Load existing credentials or create new dict
        credentials = {}
        if os.path.exists(credentials_path):
            with open(credentials_path, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode('utf-8'))

        synced_count = 0
        for secret_name in secrets:
            try:
                name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(name=name)
                secret_value = response.payload.data.decode('UTF-8')

                credentials[secret_name] = secret_value
                synced_count += 1
                print(f"  ✓ Synced: {secret_name}")

            except Exception as e:
                print(f"  ✗ Failed to sync {secret_name}: {e}")

        # Encrypt and save
        credentials_json = json.dumps(credentials, indent=2)
        encrypted_data = fernet.encrypt(credentials_json.encode('utf-8'))

        Path(credentials_path).parent.mkdir(parents=True, exist_ok=True)

        with open(credentials_path, 'wb') as f:
            f.write(encrypted_data)

        os.chmod(credentials_path, 0o600)

        print(f"\n✓ Synced {synced_count}/{len(secrets)} secrets from GCP")
        return True

    except ImportError:
        print("✗ google-cloud-secret-manager not installed")
        print("  Install with: pip install google-cloud-secret-manager")
        return False
    except Exception as e:
        print(f"✗ Error syncing from GCP: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Manage encrypted local credentials for IQRight offline mode"
    )

    parser.add_argument(
        '--generate-key',
        action='store_true',
        help='Generate a new encryption key'
    )

    parser.add_argument(
        '--add',
        nargs='+',
        metavar=('SECRET_NAME', 'SECRET_VALUE'),
        help='Add or update a credential (value is optional, will prompt if not provided)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all stored credential names'
    )

    parser.add_argument(
        '--sync-from-gcp',
        action='store_true',
        help='Sync credentials from Google Cloud Secret Manager'
    )

    parser.add_argument(
        '--credentials-path',
        default=None,
        help='Path to encrypted credentials file (default: data/credentials.iqr)'
    )

    parser.add_argument(
        '--key-path',
        default=None,
        help='Path to encryption key file (default: data/credentials.key)'
    )

    parser.add_argument(
        '--project-id',
        default=None,
        help='Google Cloud project ID (for --sync-from-gcp)'
    )

    args = parser.parse_args()

    # Set default paths
    base_path = os.environ.get('LORASERVICE_PATH', '.')
    credentials_path = args.credentials_path or os.path.join(base_path, 'data', 'credentials.iqr')
    key_path = args.key_path or os.path.join(base_path, 'data', 'credentials.key')

    # Execute commands
    if args.generate_key:
        generate_key(key_path)

    elif args.add:
        secret_name = args.add[0]
        secret_value = args.add[1] if len(args.add) > 1 else None
        add_credential(credentials_path, key_path, secret_name, secret_value)

    elif args.list:
        list_credentials(credentials_path, key_path)

    elif args.sync_from_gcp:
        # Default secrets to sync
        default_secrets = [
            'apiUsername',
            'apiPassword',
            'mqttUsername',
            'mqttpassword',
            'authServiceUrl'
        ]

        project_id = args.project_id
        if not project_id:
            try:
                from utils.config import PROJECT_ID
                project_id = PROJECT_ID
            except ImportError:
                print("✗ Project ID not found in config")
                print("  Provide with --project-id argument")
                sys.exit(1)

        sync_from_gcp(credentials_path, key_path, project_id, default_secrets)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
