#!/usr/bin/env python3
"""
Generate audio files for student names using Google Text-to-Speech.

Reads the encrypted offline data, filters students by grade,
and creates MP3 files for each student's name.

Usage:
    python utility_tools/generate_audio.py

Output:
    ./static/sounds/{external_number}.mp3
"""
import os
import sys
import pandas as pd
from io import StringIO
from cryptography.fernet import Fernet
from gtts import gTTS

# Grades to generate audio for
TARGET_GRADES = ['Third Grade', 'Fourth Grade', 'Sixth Grade']

# Paths (adjust if running from project root)
DATA_PATH = os.getenv('DATA_PATH', './data/full_load.iqr')
KEY_PATH = os.getenv('KEY_PATH', './offline.key')
OUTPUT_DIR = './static/sounds'


def decrypt_file(datafile: str, keyfile: str) -> pd.DataFrame:
    """Decrypt an .iqr file and return as DataFrame."""
    with open(keyfile, 'rb') as f:
        key = f.read()
    cipher = Fernet(key)

    with open(datafile, 'rb') as f:
        encrypted = f.read()

    decrypted = cipher.decrypt(encrypted)
    return pd.read_csv(StringIO(decrypted.decode('utf-8')))


def generate_audio(name: str, filepath: str):
    """Generate an MP3 file with the spoken student name."""
    tts = gTTS(text=name, lang='en', slow=False)
    tts.save(filepath)


def main():
    # Validate inputs
    if not os.path.exists(DATA_PATH):
        print(f"Error: Data file not found: {DATA_PATH}")
        sys.exit(1)
    if not os.path.exists(KEY_PATH):
        print(f"Error: Key file not found: {KEY_PATH}")
        sys.exit(1)

    # Load data
    print(f"Loading data from {DATA_PATH}...")
    df = decrypt_file(DATA_PATH, KEY_PATH)
    print(f"  Total records: {len(df)}")

    # Filter by grade
    filtered = df[df['HierarchyLevel1'].isin(TARGET_GRADES)].copy()
    filtered = filtered.drop_duplicates(subset=['ExternalNumber'])
    print(f"  Students in {', '.join(TARGET_GRADES)}: {len(filtered)}")

    if filtered.empty:
        print("No students found for the target grades.")
        sys.exit(0)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate audio files
    created = 0
    skipped = 0
    errors = 0

    for _, row in filtered.iterrows():
        ext_num = str(row['ExternalNumber']).strip()
        name = str(row['ChildName']).strip()

        if not ext_num or not name:
            continue

        filepath = os.path.join(OUTPUT_DIR, f"{ext_num}.mp3")

        # Skip if file already exists
        if os.path.exists(filepath):
            skipped += 1
            continue

        try:
            generate_audio(name, filepath)
            created += 1
            print(f"  [{created}] {name} -> {ext_num}.mp3")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {name} ({ext_num}): {e}")

    # Summary
    print(f"\nDone!")
    print(f"  Created: {created}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Output: {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
