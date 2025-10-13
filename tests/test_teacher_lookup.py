#!/usr/bin/env python3
"""
Integration Test: Teacher Lookup

Tests the complete flow of teacher optimization:
1. Server sends hierarchyID
2. Scanner looks up teacher name
3. Verifies actual teacher names from teachers.iqr

Can run locally with encrypted teachers.iqr file.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set LOCAL mode
os.environ["LOCAL"] = "TRUE"

import pandas as pd
from cryptography.fernet import Fernet
from io import StringIO


def load_teachers_mapping(teachers_file='./teachers.iqr', key_file='./offline.key'):
    """Load and decrypt teachers mapping"""
    try:
        # Load key
        with open(key_file, 'rb') as kf:
            key = kf.read()
        f = Fernet(key)

        # Decrypt
        with open(teachers_file, 'rb') as tf:
            encrypted_data = tf.read()

        decrypted_data = f.decrypt(encrypted_data)

        # Parse CSV
        df = pd.read_csv(StringIO(decrypted_data.decode('utf-8')), dtype={'IDHierarchy': int, 'TeacherName': str})

        # Create dictionary
        teachers_dict = {f"{row['IDHierarchy']:02d}": row['TeacherName'] for _, row in df.iterrows()}

        return teachers_dict, df

    except Exception as e:
        print(f"Error loading teachers: {e}")
        return None, None


def test_teachers_file_exists():
    """Test that teachers.iqr file exists"""
    print("Testing teachers.iqr file exists...")

    if not os.path.exists('./teachers.iqr'):
        print("  ✗ FAILED: teachers.iqr not found")
        print("     Run: python encrypt_teachers.py data/teachers_fixed.csv ./teachers.iqr")
        return False

    print("  ✓ teachers.iqr found")
    return True


def test_encryption_key_exists():
    """Test that encryption key exists"""
    print("\nTesting encryption key exists...")

    if not os.path.exists('./offline.key'):
        print("  ✗ FAILED: offline.key not found")
        return False

    print("  ✓ offline.key found")
    return True


def test_decrypt_teachers():
    """Test decryption of teachers file"""
    print("\nTesting teachers file decryption...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not decrypt teachers.iqr")
        return False

    print(f"  ✓ Successfully decrypted")
    print(f"  ✓ Loaded {len(teachers_dict)} teachers")

    return True


def test_all_hierarchies_mapped():
    """Test that all hierarchy IDs are present"""
    print("\nTesting all hierarchy IDs are mapped...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not load teachers")
        return False

    # Check specific IDs from your data
    expected_ids = [30, 40, 50, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 102, 103]

    missing = []
    for id_val in expected_ids:
        id_str = f"{id_val:02d}"
        if id_str not in teachers_dict:
            missing.append(id_val)

    if missing:
        print(f"  ✗ FAILED: Missing hierarchy IDs: {missing}")
        return False

    print(f"  ✓ All {len(expected_ids)} hierarchy IDs present")
    return True


def test_teacher_name_lookup():
    """Test lookup of specific teacher names"""
    print("\nTesting teacher name lookups...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not load teachers")
        return False

    # Test specific lookups from your actual data
    test_cases = [
        ("30", "Mrs. Liddell"),
        ("40", "Mrs Tiaga"),
        ("50", "Mr Gouveia"),
        ("83", "Mrs. Olga Griffin"),
        ("84", "Miss Emily Boutin"),
        ("85", "Mrs. Leigh Anne Aldama"),
        ("90", "Miss Julia Necessary"),
        ("94", "Mrs. Melissa McCarty"),
        ("99", "Mrs. Kaley Hefley"),
        ("102", "Mrs. Carla Pardetti"),
    ]

    passed = 0
    failed = 0

    for hierarchy_id, expected_name in test_cases:
        actual_name = teachers_dict.get(hierarchy_id)

        if actual_name == expected_name:
            print(f"  ✓ {hierarchy_id} → {expected_name}")
            passed += 1
        else:
            print(f"  ✗ FAILED: {hierarchy_id} → Expected: '{expected_name}', Got: '{actual_name}'")
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed")
    return failed == 0


def test_payload_format():
    """Test server payload format with hierarchyID"""
    print("\nTesting payload format...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not load teachers")
        return False

    # Simulate server sending data
    student_name = "Emma Smith"
    grade = "3rd"
    hierarchy_id = "83"  # Mrs. Olga Griffin

    # Server sends this
    server_payload = f"{student_name}|{grade}|{hierarchy_id}"
    print(f"  Server sends: '{server_payload}'")

    # Scanner receives and parses
    parts = server_payload.split("|")
    received_name = parts[0]
    received_grade = parts[1]
    received_id = parts[2]

    # Scanner looks up teacher
    teacher_name = teachers_dict.get(received_id, f"Teacher {received_id}")

    print(f"  Scanner displays: '{received_name}' | '{received_grade}' | '{teacher_name}'")

    # Verify
    if teacher_name == "Mrs. Olga Griffin":
        print(f"  ✓ Teacher lookup successful")
        return True
    else:
        print(f"  ✗ FAILED: Expected 'Mrs. Olga Griffin', got '{teacher_name}'")
        return False


def test_fallback_behavior():
    """Test fallback when hierarchy ID not found"""
    print("\nTesting fallback behavior...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not load teachers")
        return False

    # Test with non-existent ID
    unknown_id = "99999"  # Doesn't exist
    fallback_name = teachers_dict.get(unknown_id, f"Teacher {unknown_id}")

    if fallback_name == f"Teacher {unknown_id}":
        print(f"  ✓ Fallback works: Unknown ID '{unknown_id}' → '{fallback_name}'")
        return True
    else:
        print(f"  ✗ FAILED: Fallback didn't work properly")
        return False


def test_display_all_teachers():
    """Display all teachers for verification"""
    print("\nDisplaying all teachers in mapping...")

    teachers_dict, df = load_teachers_mapping()

    if teachers_dict is None:
        print("  ✗ FAILED: Could not load teachers")
        return False

    print(f"\n{'ID':<6} {'Teacher Name':<30}")
    print("=" * 40)

    for hierarchy_id in sorted(teachers_dict.keys(), key=lambda x: int(x)):
        teacher_name = teachers_dict[hierarchy_id]
        print(f"{hierarchy_id:<6} {teacher_name:<30}")

    print("=" * 40)
    print(f"Total: {len(teachers_dict)} teachers")

    return True


def main():
    """Run all teacher lookup tests"""
    print("=" * 60)
    print("TEACHER LOOKUP INTEGRATION TESTS")
    print("=" * 60)

    tests = [
        test_teachers_file_exists,
        test_encryption_key_exists,
        test_decrypt_teachers,
        test_all_hierarchies_mapped,
        test_teacher_name_lookup,
        test_payload_format,
        test_fallback_behavior,
        test_display_all_teachers,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
