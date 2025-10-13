#!/usr/bin/env python3
"""
Unit Test: CRC Validation

Tests that CRC16 detects corrupted packets.
Can run locally without LoRa radio.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lora import LoRaPacket, PacketType


def test_crc_validation():
    """Test CRC detects corrupted packets"""
    print("Testing CRC validation with corrupted payload...")

    # Create packet
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test_payload_12345",
        sequence_num=1
    )

    data = packet.serialize()
    print(f"  ✓ Original packet: {len(data)} bytes")

    # Corrupt a byte in the payload (after header)
    corrupted = bytearray(data)
    corrupted[25] ^= 0xFF  # Flip all bits in one byte

    # Try to deserialize
    result = LoRaPacket.deserialize(bytes(corrupted))

    assert result is None, "CRC should have detected corruption"
    print(f"  ✓ Corrupted packet rejected (CRC mismatch detected)")
    return True


def test_crc_header_corruption():
    """Test CRC detects header corruption"""
    print("\nTesting CRC validation with corrupted header...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=42
    )

    data = packet.serialize()

    # Corrupt sequence number in header (bytes 12-13)
    corrupted = bytearray(data)
    corrupted[12] ^= 0xFF

    result = LoRaPacket.deserialize(bytes(corrupted))

    assert result is None, "CRC should have detected header corruption"
    print(f"  ✓ Header corruption detected by CRC")
    return True


def test_crc_valid_packet():
    """Test that valid packets pass CRC"""
    print("\nTesting CRC validation with valid packet...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"valid_packet",
        sequence_num=1
    )

    data = packet.serialize()
    result = LoRaPacket.deserialize(data)

    assert result is not None, "Valid packet should pass CRC"
    assert result.payload == b"valid_packet"
    print(f"  ✓ Valid packet passes CRC validation")
    return True


def test_crc_multiple_corruptions():
    """Test various corruption patterns"""
    print("\nTesting multiple corruption patterns...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test_multiple_corruption_patterns",
        sequence_num=1
    )

    data = packet.serialize()
    corruptions_tested = 0

    # Test corruption at various positions
    for pos in [0, 5, 10, 15, 20, 25, 30]:
        if pos >= len(data) - 2:  # Don't corrupt CRC itself
            continue

        corrupted = bytearray(data)
        corrupted[pos] ^= 0x01  # Flip one bit

        result = LoRaPacket.deserialize(bytes(corrupted))
        assert result is None, f"Corruption at position {pos} not detected"
        corruptions_tested += 1

    print(f"  ✓ All {corruptions_tested} corruption patterns detected")
    return True


def test_crc_boundary_conditions():
    """Test CRC with edge cases"""
    print("\nTesting CRC boundary conditions...")

    # Empty payload
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"",
        sequence_num=1
    )

    data = packet.serialize()
    result = LoRaPacket.deserialize(data)
    assert result is not None, "Empty payload should be valid"
    print(f"  ✓ Empty payload: CRC valid")

    # Single byte payload
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"X",
        sequence_num=1
    )

    data = packet.serialize()
    result = LoRaPacket.deserialize(data)
    assert result is not None, "Single byte payload should be valid"
    print(f"  ✓ Single byte payload: CRC valid")

    return True


def main():
    """Run all CRC validation tests"""
    print("=" * 60)
    print("CRC VALIDATION TESTS (LOCAL - NO HARDWARE REQUIRED)")
    print("=" * 60)

    tests = [
        test_crc_validation,
        test_crc_header_corruption,
        test_crc_valid_packet,
        test_crc_multiple_corruptions,
        test_crc_boundary_conditions
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
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
