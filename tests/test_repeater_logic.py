#!/usr/bin/env python3
"""
Unit Test: Repeater Logic

Tests repeater packet forwarding, TTL decrement, and sender update.
Can run locally without LoRa radio.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lora import LoRaPacket, PacketType, PacketFlags


def test_repeater_create_repeat():
    """Test creating repeated packet"""
    print("Testing repeater packet creation...")

    # Original packet from scanner to server
    original = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,  # Scanner
        dest_node=1,      # Server
        payload=b"102|123456789|1",
        sequence_num=42,
        ttl=3
    )

    # Repeater forwards packet
    repeated = original.create_repeat(repeater_node_id=200)

    # Verify fields
    assert repeated.source_node == 102, "Source should remain scanner"
    assert repeated.dest_node == 1, "Destination should remain server"
    assert repeated.sender_node == 200, "Sender should be repeater"
    assert repeated.sequence_num == 42, "Sequence should be preserved"
    assert repeated.ttl == 2, "TTL should be decremented"
    assert repeated.flags & PacketFlags.IS_REPEAT, "Should have IS_REPEAT flag"
    assert repeated.payload == b"102|123456789|1", "Payload should be preserved"

    print(f"  ✓ Original: src={original.source_node}, sender={original.sender_node}, ttl={original.ttl}")
    print(f"  ✓ Repeated: src={repeated.source_node}, sender={repeated.sender_node}, ttl={repeated.ttl}")
    print(f"  ✓ IS_REPEAT flag set: {bool(repeated.flags & PacketFlags.IS_REPEAT)}")

    return True


def test_ttl_decrement_chain():
    """Test TTL decrement through multiple repeaters"""
    print("\nTesting TTL decrement chain...")

    # Start with TTL=3
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=1,
        ttl=3
    )

    print(f"  ✓ Initial: src={packet.source_node}, sender={packet.sender_node}, ttl={packet.ttl}")

    # Repeater 1 (node 200)
    packet = packet.create_repeat(200)
    assert packet.ttl == 2, "TTL should be 2 after first repeater"
    print(f"  ✓ After repeater 200: sender={packet.sender_node}, ttl={packet.ttl}")

    # Repeater 2 (node 201)
    packet = packet.create_repeat(201)
    assert packet.ttl == 1, "TTL should be 1 after second repeater"
    print(f"  ✓ After repeater 201: sender={packet.sender_node}, ttl={packet.ttl}")

    # Repeater 3 (node 202)
    packet = packet.create_repeat(202)
    assert packet.ttl == 0, "TTL should be 0 after third repeater"
    print(f"  ✓ After repeater 202: sender={packet.sender_node}, ttl={packet.ttl}")

    # TTL=0 should be dropped by next repeater
    from lora import NodeType
    should_process, reason = packet.should_process(203, NodeType.REPEATER, set())
    assert not should_process, "TTL=0 should be dropped"
    assert reason == "ttl_expired"
    print(f"  ✓ TTL=0 packet dropped by repeater 203: reason={reason}")

    return True


def test_repeater_preserves_payload():
    """Test repeater preserves payload exactly"""
    print("\nTesting repeater preserves payload...")

    # Create packet with various payload types
    test_payloads = [
        b"simple",
        b"102|123456789|1",
        b"cmd|ack|break",
        b"Name|Grade|Teacher",
        b"Special chars: \x00\x01\xff"
    ]

    for payload in test_payloads:
        original = LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=102,
            dest_node=1,
            payload=payload,
            sequence_num=1,
            ttl=3
        )

        repeated = original.create_repeat(200)

        assert repeated.payload == payload, f"Payload mismatch: {repeated.payload} != {payload}"

    print(f"  ✓ All {len(test_payloads)} payload types preserved")

    return True


def test_repeater_serialization():
    """Test repeated packet serialization/deserialization"""
    print("\nTesting repeated packet serialization...")

    # Original packet
    original = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test_data",
        sequence_num=42,
        ttl=3
    )

    # Repeater forwards
    repeated = original.create_repeat(200)

    # Serialize
    data = repeated.serialize()

    # Deserialize
    reconstructed = LoRaPacket.deserialize(data)

    assert reconstructed is not None, "Deserialization failed"
    assert reconstructed.source_node == 102, "Source mismatch"
    assert reconstructed.sender_node == 200, "Sender mismatch"
    assert reconstructed.ttl == 2, "TTL mismatch"
    assert reconstructed.flags & PacketFlags.IS_REPEAT, "IS_REPEAT flag missing"

    print(f"  ✓ Repeated packet serialized/deserialized correctly")
    print(f"  ✓ Reconstructed: src={reconstructed.source_node}, sender={reconstructed.sender_node}, ttl={reconstructed.ttl}")

    return True


def test_multi_hop_path():
    """Test packet path through multiple hops"""
    print("\nTesting multi-hop path tracking...")

    # Scanner -> Repeater1 -> Repeater2 -> Server
    hops = [
        (102, "Scanner"),      # Original sender
        (200, "Repeater1"),
        (201, "Repeater2")
    ]

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"multi_hop_test",
        sequence_num=1,
        ttl=4
    )

    print(f"  ✓ Initial: src={packet.source_node}, sender={packet.sender_node}, ttl={packet.ttl}")

    for node_id, name in hops[1:]:  # Skip scanner (original sender)
        packet = packet.create_repeat(node_id)
        print(f"  ✓ Via {name}: sender={packet.sender_node}, ttl={packet.ttl}")
        assert packet.source_node == 102, "Source should always be scanner"
        assert packet.sender_node == node_id, f"Sender should be {name}"

    print(f"  ✓ Path complete: {hops[0][1]} -> {hops[1][1]} -> {hops[2][1]} -> Server")

    return True


def test_repeater_timestamp_preservation():
    """Test that repeater preserves original timestamp"""
    print("\nTesting repeater preserves timestamp...")

    original = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=1,
        ttl=3
    )

    original_timestamp = original.timestamp

    # Forward through repeater
    repeated = original.create_repeat(200)

    assert repeated.timestamp == original_timestamp, "Timestamp should be preserved"
    print(f"  ✓ Timestamp preserved: {original_timestamp}")

    return True


def test_repeater_multi_packet_preservation():
    """Test repeater preserves multi-packet sequence info"""
    print("\nTesting repeater preserves multi-packet info...")

    from lora import MultiPartFlags

    # Create multi-part packet
    original = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"Student 1",
        sequence_num=1,
        ttl=3,
        multi_flags=MultiPartFlags.FIRST | MultiPartFlags.MORE,
        multi_part_index=1,
        multi_part_total=3
    )

    # Forward through repeater
    repeated = original.create_repeat(200)

    # Verify multi-packet info preserved
    assert repeated.multi_flags == original.multi_flags, "Multi-flags should be preserved"
    assert repeated.multi_part_index == original.multi_part_index, "Index should be preserved"
    assert repeated.multi_part_total == original.multi_part_total, "Total should be preserved"
    assert repeated.is_multi_part(), "Should still be multi-part"

    print(f"  ✓ Multi-packet info preserved: [{repeated.multi_part_index}/{repeated.multi_part_total}]")

    return True


def main():
    """Run all repeater logic tests"""
    print("=" * 60)
    print("REPEATER LOGIC TESTS (LOCAL - NO HARDWARE REQUIRED)")
    print("=" * 60)

    tests = [
        test_repeater_create_repeat,
        test_ttl_decrement_chain,
        test_repeater_preserves_payload,
        test_repeater_serialization,
        test_multi_hop_path,
        test_repeater_timestamp_preservation,
        test_repeater_multi_packet_preservation
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
