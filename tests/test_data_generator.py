#!/usr/bin/env python3
"""
Test Data Generator

Generates dummy student data for testing purposes.
"""

import json
import random

# Sample data
FIRST_NAMES = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
    "Lucas", "Harper", "Henry", "Evelyn", "Alexander"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]

GRADES = [
    "Kindergarten", "First Grade", "Second Grade", "Third Grade",
    "Fourth Grade", "Fifth Grade", "Sixth Grade", "Seventh Grade", "Eighth Grade"
]

TEACHERS = [
    "Mrs. Anderson", "Mr. Thompson", "Ms. Garcia", "Mrs. Wilson",
    "Mr. Davis", "Ms. Martinez", "Mrs. Brown", "Mr. Johnson",
    "Ms. Smith", "Mrs. Miller"
]

HIERARCHIES = [
    {"id": 30, "level1": "Kindergarten", "level2": "Mrs. Liddell"},
    {"id": 40, "level1": "First Grade", "level2": "Mrs Tiaga"},
    {"id": 50, "level1": "Second Grade", "level2": "Mr Gouveia"},
    {"id": 83, "level1": "Third Grade", "level2": "Mrs. Olga Griffin"},
    {"id": 84, "level1": "Third Grade", "level2": "Miss Emily Boutin"},
    {"id": 85, "level1": "Fourth Grade", "level2": "Mrs. Leigh Anne Aldama"},
    {"id": 86, "level1": "Fourth Grade", "level2": "Mrs. Katy Ramos"},
    {"id": 87, "level1": "Fifth Grade", "level2": "Miss Litzi Perea"},
    {"id": 88, "level1": "Fifth Grade", "level2": "Mrs. Jamie Bell"},
    {"id": 89, "level1": "Sixth Grade", "level2": "Mrs. Amanda Stephens"},
    {"id": 90, "level1": "Sixth Grade", "level2": "Miss Julia Necessary"},
    {"id": 91, "level1": "Seventh Grade", "level2": "Mrs. Hazel Chidyausiku"},
    {"id": 92, "level1": "Seventh Grade", "level2": "Miss Jadyn Heinle"},
    {"id": 93, "level1": "Eighth Grade", "level2": "Mrs. Marisean Grom"},
    {"id": 94, "level1": "Eighth Grade", "level2": "Mrs. Melissa McCarty"},
]


def generate_qr_code():
    """Generate random QR code (9 digits)"""
    return str(random.randint(100000000, 999999999))


def generate_student():
    """Generate a single student record"""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    hierarchy = random.choice(HIERARCHIES)

    return {
        "name": f"{first_name} {last_name}",
        "hierarchyLevel1": hierarchy["level1"],
        "hierarchyLevel2": hierarchy["level2"],  # This is still in local DB but not sent over LoRa
        "hierarchyID": f"{hierarchy['id']:02d}",  # 2-digit ID sent over LoRa instead (e.g., "30", "40", "83")
        "externalNumber": generate_qr_code(),
        "externalID": generate_qr_code(),
        "distance": random.randint(1, 5),
        "node": 102,
        "location": "Main Entrance"
    }


def generate_students(count=10):
    """Generate multiple student records"""
    return [generate_student() for _ in range(count)]


def generate_scan_request(beacon=102, qr_code=None):
    """Generate scanner request payload"""
    if qr_code is None:
        qr_code = generate_qr_code()
    return f"{beacon}|{qr_code}|1"


def generate_command(command):
    """Generate command payload"""
    return f"cmd:{command}"


def save_test_data(filename="test_data.json"):
    """Save generated test data to file"""
    data = {
        "students": generate_students(20),
        "qr_codes": [generate_qr_code() for _ in range(10)],
        "scan_requests": [generate_scan_request() for _ in range(10)],
        "commands": [
            generate_command("break"),
            generate_command("release"),
            generate_command("undo"),
            generate_command("cleanup")
        ]
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Generated test data saved to: {filename}")
    print(f"  - {len(data['students'])} students")
    print(f"  - {len(data['qr_codes'])} QR codes")
    print(f"  - {len(data['scan_requests'])} scan requests")
    print(f"  - {len(data['commands'])} commands")

    return data


def print_sample_data():
    """Print sample data for inspection"""
    print("=" * 60)
    print("SAMPLE TEST DATA")
    print("=" * 60)

    print("\nSample Student:")
    student = generate_student()
    for key, value in student.items():
        print(f"  {key}: {value}")

    print("\nSample QR Codes:")
    for i in range(5):
        print(f"  {i+1}. {generate_qr_code()}")

    print("\nSample Scan Requests:")
    for i in range(5):
        print(f"  {i+1}. {generate_scan_request()}")

    print("\nSample Commands:")
    for cmd in ["break", "release", "undo", "cleanup"]:
        print(f"  - {generate_command(cmd)}")

    print("=" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        filename = sys.argv[2] if len(sys.argv) > 2 else "test_data.json"
        save_test_data(filename)
    else:
        print_sample_data()
        print("\nTo save test data to file, run:")
        print("  python test_data_generator.py --save [filename.json]")
