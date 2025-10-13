#!/usr/bin/env python3
"""
Unit Test: Packet Serialization/Deserialization

Tests packet roundtrip (serialize -> deserialize) without hardware.
Can run locally without LoRa radio.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lora import LoRaPacket, PacketType, MultiPartFlags


def test_packet_roundtrip():
    """Test packet serialization and deserialization"""
    print("Testing packet serialization/deserialization...")

    # Create packet
    original = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"102|123456789|1",
        sequence_num=42,
        ttl=3
    )

    # Serialize
    data = original.serialize()
    print(f"  ✓ Serialized packet: {len(data)} bytes")

    # Deserialize
    reconstructed = LoRaPacket.deserialize(data)

    # Validate
    assert reconstructed is not None, "Deserialization failed"
    assert reconstructed.source_node == 102, f"Source node mismatch: {reconstructed.source_node}"
    assert reconstructed.dest_node == 1, f"Dest node mismatch: {reconstructed.dest_node}"
    assert reconstructed.sequence_num == 42, f"Sequence number mismatch: {reconstructed.sequence_num}"
    assert reconstructed.ttl == 3, f"TTL mismatch: {reconstructed.ttl}"
    assert reconstructed.payload == b"102|123456789|1", f"Payload mismatch: {reconstructed.payload}"

    print(f"  ✓ Deserialized packet matches original")
    print(f"  ✓ Packet: {reconstructed}")
    return True


def test_packet_with_large_payload():
    """Test packet with maximum payload size"""
    print("\nTesting packet with large payload...")

    # Create max-size payload (231 bytes)
    max_payload = b"X" * LoRaPacket.MAX_PAYLOAD

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=max_payload,
        sequence_num=1
    )

    data = packet.serialize()
    print(f"  ✓ Serialized large packet: {len(data)} bytes")

    reconstructed = LoRaPacket.deserialize(data)
    assert reconstructed is not None, "Deserialization failed"
    assert len(reconstructed.payload) == LoRaPacket.MAX_PAYLOAD
    print(f"  ✓ Large payload ({len(reconstructed.payload)} bytes) handled correctly")
    return True


def test_packet_truncation():
    """Test that oversized payload is truncated"""
    print("\nTesting payload truncation...")

    # Create oversized payload (300 bytes)
    oversized_payload = b"Y" * 300

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=oversized_payload,
        sequence_num=1
    )

    # Should be truncated to MAX_PAYLOAD
    assert len(packet.payload) == LoRaPacket.MAX_PAYLOAD
    print(f"  ✓ Oversized payload truncated from 300 to {len(packet.payload)} bytes")

    # Test serialization still works
    data = packet.serialize()
    reconstructed = LoRaPacket.deserialize(data)
    assert reconstructed is not None
    print(f"  ✓ Truncated packet serializes/deserializes correctly")
    return True


def test_all_packet_types():
    """Test serialization of all packet types"""
    print("\nTesting all packet types...")

    packet_types = [PacketType.DATA, PacketType.ACK, PacketType.CMD, PacketType.BEACON]

    for pkt_type in packet_types:
        packet = LoRaPacket.create(
            packet_type=pkt_type,
            source_node=102,
            dest_node=1,
            payload=f"test_{pkt_type.name}".encode('utf-8'),
            sequence_num=1
        )

        data = packet.serialize()
        reconstructed = LoRaPacket.deserialize(data)

        assert reconstructed is not None, f"Failed for type {pkt_type.name}"
        assert reconstructed.packet_type == pkt_type, f"Type mismatch for {pkt_type.name}"
        print(f"  ✓ {pkt_type.name} packet: OK")

    return True


def main():
    """Run all serialization tests"""
    print("=" * 60)
    print("PACKET SERIALIZATION TESTS (LOCAL - NO HARDWARE REQUIRED)")
    print("=" * 60)

    tests = [
        test_packet_roundtrip,
        test_packet_with_large_payload,
        test_packet_truncation,
        test_all_packet_types
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
