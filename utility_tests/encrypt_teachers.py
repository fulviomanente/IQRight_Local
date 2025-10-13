#!/usr/bin/env python3
"""
Encrypt Teachers File

Encrypts a CSV file containing teacher/hierarchy mappings for use by scanners.

Input CSV Format:
IDHierarchy,TeacherName
1,Mrs. Anderson
2,Mr. Thompson
...

Usage:
    python encrypt_teachers.py teachers.csv

Output:
    /etc/iqright/LoraService/data/teachers.iqr (encrypted)
    or ./teachers.iqr (if LOCAL=TRUE)
"""

import os
import sys
import pandas as pd
from cryptography.fernet import Fernet
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

# Paths
if os.getenv('LOCAL', None) == 'TRUE':
    DATA_PATH = '..'
    KEY_PATH = '../offline.key'
else:
    DATA_PATH = '/etc/iqright/LoraService/data'
    KEY_PATH = '/etc/iqright/LoraService/offline.key'


def load_or_create_key(key_path: str) -> bytes:
    """Load existing encryption key or create new one"""
    if os.path.exists(key_path):
        with open(key_path, 'rb') as key_file:
            key = key_file.read()
        print(f"✓ Loaded existing key from: {key_path}")
        return key
    else:
        print(f"⚠️  Key not found at {key_path}")
        print(f"   Creating new key...")
        key = Fernet.generate_key()
        with open(key_path, 'wb') as key_file:
            key_file.write(key)
        print(f"✓ New key created: {key_path}")
        return key


def encrypt_teachers_file(input_csv: str, output_iqr: str = None, key_path: str = KEY_PATH):
    """Encrypt teachers CSV file"""

    # Default output path
    if output_iqr is None:
        output_iqr = os.path.join(DATA_PATH, 'teachers.iqr')

    # Create data directory if needed
    os.makedirs(os.path.dirname(output_iqr), exist_ok=True)

    print("=" * 60)
    print("ENCRYPTING TEACHERS FILE")
    print("=" * 60)

    # Load CSV
    print(f"\n1. Reading CSV: {input_csv}")
    try:
        df = pd.read_csv(input_csv, dtype={'IDHierarchy': int, 'TeacherName': str})
    except FileNotFoundError:
        print(f"✗ Error: File not found: {input_csv}")
        return False
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return False

    print(f"   ✓ Loaded {len(df)} teachers")
    print(f"\n   Preview:")
    print(df.head().to_string(index=False))

    # Validate required columns
    required_cols = ['IDHierarchy', 'TeacherName']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"✗ Error: Missing required columns: {missing_cols}")
        print(f"   Expected: {required_cols}")
        print(f"   Found: {list(df.columns)}")
        return False

    # Load or create encryption key
    print(f"\n2. Loading encryption key: {key_path}")
    try:
        key = load_or_create_key(key_path)
        f = Fernet(key)
    except Exception as e:
        print(f"✗ Error loading key: {e}")
        return False

    # Convert to CSV string
    print(f"\n3. Converting to CSV format")
    csv_string = df.to_csv(index=False)
    csv_bytes = csv_string.encode('utf-8')
    print(f"   ✓ CSV size: {len(csv_bytes)} bytes")

    # Encrypt
    print(f"\n4. Encrypting data")
    try:
        encrypted_data = f.encrypt(csv_bytes)
        print(f"   ✓ Encrypted size: {len(encrypted_data)} bytes")
    except Exception as e:
        print(f"✗ Error encrypting: {e}")
        return False

    # Write encrypted file
    print(f"\n5. Writing encrypted file: {output_iqr}")
    try:
        with open(output_iqr, 'wb') as encrypted_file:
            encrypted_file.write(encrypted_data)
        print(f"   ✓ File written successfully")
    except Exception as e:
        print(f"✗ Error writing file: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ ENCRYPTION COMPLETE")
    print("=" * 60)
    print(f"\nEncrypted file: {output_iqr}")
    print(f"Encryption key: {key_path}")
    print(f"Teachers count: {len(df)}")
    print(f"\n⚠️  Keep the encryption key secure!")
    print(f"   Scanners will need both files to decrypt.")

    return True


def decrypt_and_verify(encrypted_file: str, key_path: str = KEY_PATH):
    """Decrypt and verify the encrypted file"""
    print("\n" + "=" * 60)
    print("VERIFYING ENCRYPTED FILE")
    print("=" * 60)

    try:
        # Load key
        with open(key_path, 'rb') as key_file:
            key = key_file.read()
        f = Fernet(key)

        # Decrypt
        with open(encrypted_file, 'rb') as enc_file:
            encrypted_data = enc_file.read()

        decrypted_data = f.decrypt(encrypted_data)

        # Parse CSV
        df = pd.read_csv(StringIO(decrypted_data.decode('utf-8')))

        print(f"✓ Decryption successful")
        print(f"✓ {len(df)} teachers loaded")
        print(f"\nDecrypted data:")
        print(df.to_string(index=False))

        return True

    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False


def create_sample_teachers_csv(filename: str = "teachers_sample.csv"):
    """Create a sample teachers CSV file for testing"""
    sample_data = {
        'IDHierarchy': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'TeacherName': [
            'Mrs. Anderson',
            'Mr. Thompson',
            'Ms. Garcia',
            'Mrs. Wilson',
            'Mr. Davis',
            'Ms. Martinez',
            'Mrs. Brown',
            'Mr. Johnson',
            'Ms. Smith',
            'Mrs. Miller'
        ]
    }

    df = pd.DataFrame(sample_data)
    df.to_csv(filename, index=False)

    print(f"✓ Sample file created: {filename}")
    print(f"\nContents:")
    print(df.to_string(index=False))

    return filename


def main():
    if len(sys.argv) < 2:
        print("Usage: python encrypt_teachers.py <teachers.csv> [output.iqr]")
        print("\nOptions:")
        print("  --sample    Create a sample teachers.csv file")
        print("  --verify    Verify encrypted file can be decrypted")
        print("\nExamples:")
        print("  python encrypt_teachers.py --sample")
        print("  python encrypt_teachers.py teachers.csv")
        print("  python encrypt_teachers.py teachers.csv /path/to/output.iqr")
        print("  python encrypt_teachers.py --verify teachers.iqr")
        sys.exit(1)

    # Handle special commands
    if sys.argv[1] == '--sample':
        sample_file = create_sample_teachers_csv()
        print(f"\nNow encrypt it with:")
        print(f"  python encrypt_teachers.py {sample_file}")
        sys.exit(0)

    if sys.argv[1] == '--verify':
        if len(sys.argv) < 3:
            print("Error: --verify requires encrypted file path")
            print("Usage: python encrypt_teachers.py --verify <encrypted.iqr>")
            sys.exit(1)

        success = decrypt_and_verify(sys.argv[2])
        sys.exit(0 if success else 1)

    # Encrypt file
    input_csv = sys.argv[1]
    output_iqr = sys.argv[2] if len(sys.argv) > 2 else None

    success = encrypt_teachers_file(input_csv, output_iqr)

    if success and output_iqr:
        # Verify
        print(f"\n")
        decrypt_and_verify(output_iqr or os.path.join(DATA_PATH, 'teachers.iqr'))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
