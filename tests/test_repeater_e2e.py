#!/usr/bin/env python3
"""
End-to-End Repeater Tests

Tests complete packet flow through repeater with collision avoidance:
1. Scanner → Repeater → Server
2. Server → Repeater → Scanner
3. Multi-hop (Scanner → Repeater1 → Repeater2 → Server)
4. Collision avoidance mechanisms
5. Duplicate detection
6. TTL expiration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set LOCAL mode
os.environ["LOCAL"] = "TRUE"

from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, CollisionAvoidance
import time


def test_scanner_to_server_via_repeater():
    """Test: Scanner → Repeater → Server"""
    print("Testing: Scanner → Repeater → Server...")

    # Create nodes
    scanner = LoRaTransceiver(node_id=102, node_type=NodeType.SCANNER)
    repeater = LoRaTransceiver(node_id=200, node_type=NodeType.REPEATER)
    server = LoRaTransceiver(node_id=1, node_type=NodeType.SERVER)

    # Scanner creates packet
    original_packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"SCAN123456",
        sequence_num=100,
        ttl=3
    )

    print(f"  Original packet: src={original_packet.source_node}, sender={original_packet.sender_node}, ttl={original_packet.ttl}")

    # Repeater receives and processes
    should_process, reason = original_packet.should_process(200, NodeType.REPEATER, set())
    assert should_process, f"Repeater should process packet, got: {reason}"

    # Repeater forwards (updated sender, decremented TTL)
    repeated_packet = original_packet.create_repeat(200)
    assert repeated_packet.source_node == 102, "Source should remain scanner"
    assert repeated_packet.sender_node == 200, "Sender should be repeater"
    assert repeated_packet.ttl == 2, "TTL should decrement"
    assert repeated_packet.is_repeat, "IS_REPEAT flag should be set"
    assert repeated_packet.payload == b"SCAN123456", "Payload should be preserved"

    print(f"  Repeated packet: src={repeated_packet.source_node}, sender={repeated_packet.sender_node}, ttl={repeated_packet.ttl}")

    # Server receives
    should_process, reason = repeated_packet.should_process(1, NodeType.SERVER, set())
    assert should_process, f"Server should process packet, got: {reason}"
    assert repeated_packet.dest_node == 1, "Destination should be server"

    print("  ✓ Packet successfully forwarded from scanner to server")
    return True


def test_server_to_scanner_via_repeater():
    """Test: Server → Repeater → Scanner (response flow)"""
    print("\nTesting: Server → Repeater → Scanner (response)...")

    # Server sends response to scanner
    response_packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"John Doe|3rd|83",
        sequence_num=200,
        ttl=3
    )

    print(f"  Response packet: src={response_packet.source_node}, dest={response_packet.dest_node}, ttl={response_packet.ttl}")

    # Repeater processes
    should_process, reason = response_packet.should_process(200, NodeType.REPEATER, set())
    assert should_process, f"Repeater should forward response, got: {reason}"

    # Forward to scanner
    repeated_response = response_packet.create_repeat(200)
    assert repeated_response.dest_node == 102, "Destination should be scanner"
    assert repeated_response.sender_node == 200, "Sender should be repeater"
    assert repeated_response.ttl == 2, "TTL should decrement"

    print(f"  Forwarded response: sender={repeated_response.sender_node}, ttl={repeated_response.ttl}")

    # Scanner receives
    should_process, reason = repeated_response.should_process(102, NodeType.SCANNER, set())
    assert should_process, f"Scanner should process response, got: {reason}"

    print("  ✓ Response successfully forwarded from server to scanner")
    return True


def test_multi_hop_chain():
    """Test: Scanner → Repeater1 → Repeater2 → Server"""
    print("\nTesting: Multi-hop chain (Scanner → R1 → R2 → Server)...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"MULTIHOP",
        sequence_num=300,
        ttl=4
    )

    print(f"  Initial: src={packet.source_node}, sender={packet.sender_node}, ttl={packet.ttl}")

    # Hop 1: Scanner → Repeater1
    should_process, _ = packet.should_process(200, NodeType.REPEATER, set())
    assert should_process, "Repeater1 should process"
    packet = packet.create_repeat(200)
    assert packet.ttl == 3 and packet.sender_node == 200
    print(f"  After Repeater1: sender={packet.sender_node}, ttl={packet.ttl}")

    # Hop 2: Repeater1 → Repeater2
    should_process, _ = packet.should_process(201, NodeType.REPEATER, set())
    assert should_process, "Repeater2 should process"
    packet = packet.create_repeat(201)
    assert packet.ttl == 2 and packet.sender_node == 201
    print(f"  After Repeater2: sender={packet.sender_node}, ttl={packet.ttl}")

    # Hop 3: Repeater2 → Server
    should_process, _ = packet.should_process(1, NodeType.SERVER, set())
    assert should_process, "Server should process"
    assert packet.source_node == 102, "Original source preserved"
    assert packet.payload == b"MULTIHOP", "Payload preserved"

    print("  ✓ Multi-hop chain successful (4 hops, TTL managed correctly)")
    return True


def test_duplicate_detection():
    """Test: Repeater rejects duplicate packets"""
    print("\nTesting: Duplicate detection...")

    repeater_seen = set()

    packet1 = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"TEST",
        sequence_num=100,
        ttl=3
    )

    # First time: should process
    should_process, reason = packet1.should_process(200, NodeType.REPEATER, repeater_seen)
    assert should_process, f"First packet should be processed, got: {reason}"
    repeater_seen.add((packet1.source_node, packet1.sequence_num))
    print(f"  First packet (seq={packet1.sequence_num}): processed ✓")

    # Same packet again: should reject
    should_process, reason = packet1.should_process(200, NodeType.REPEATER, repeater_seen)
    assert not should_process, "Duplicate should be rejected"
    assert reason == "duplicate", f"Expected 'duplicate', got '{reason}'"
    print(f"  Duplicate packet (seq={packet1.sequence_num}): rejected ✓")

    # Different sequence: should process
    packet2 = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"TEST2",
        sequence_num=101,
        ttl=3
    )
    should_process, reason = packet2.should_process(200, NodeType.REPEATER, repeater_seen)
    assert should_process, f"New packet should be processed, got: {reason}"
    print(f"  New packet (seq={packet2.sequence_num}): processed ✓")

    print("  ✓ Duplicate detection working correctly")
    return True


def test_ttl_expiration():
    """Test: Packet with TTL=0 is dropped"""
    print("\nTesting: TTL expiration...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"EXPIRED",
        sequence_num=400,
        ttl=1
    )

    # Repeater1 processes (TTL 1 → 0)
    should_process, _ = packet.should_process(200, NodeType.REPEATER, set())
    assert should_process, "Should process with TTL=1"
    packet = packet.create_repeat(200)
    assert packet.ttl == 0, "TTL should be 0 after repeat"
    print(f"  After Repeater1: ttl={packet.ttl}")

    # Repeater2 should drop (TTL=0)
    should_process, reason = packet.should_process(201, NodeType.REPEATER, set())
    assert not should_process, "Should not process with TTL=0"
    assert reason == "ttl_expired", f"Expected 'ttl_expired', got '{reason}'"
    print(f"  Repeater2 drops packet: {reason} ✓")

    print("  ✓ TTL expiration prevents infinite loops")
    return True


def test_loop_detection():
    """Test: Repeater detects its own packets (loop prevention)"""
    print("\nTesting: Loop detection...")

    # Repeater 200 forwards a packet, then receives it again
    original_packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"LOOP",
        sequence_num=500,
        ttl=3
    )

    # Simulate repeater 200 forwarding it (sender becomes 200)
    packet = original_packet.create_repeat(200)

    # Same repeater 200 receives it again (loop!)
    should_process, reason = packet.should_process(200, NodeType.REPEATER, set())
    assert not should_process, "Should detect loop"
    assert reason == "own_packet_looped", f"Expected 'own_packet_looped', got '{reason}'"
    print(f"  Repeater detected own packet: {reason} ✓")

    print("  ✓ Loop detection prevents re-forwarding own packets")
    return True


def test_collision_avoidance_delay():
    """Test: Collision avoidance adds randomized delay"""
    print("\nTesting: Collision avoidance delay...")

    # Measure randomized delay
    start = time.time()
    CollisionAvoidance.randomized_delay(min_ms=10, max_ms=50)
    elapsed = time.time() - start

    assert 0.01 <= elapsed <= 0.1, f"Delay should be 10-50ms, got {elapsed*1000:.1f}ms"
    print(f"  Random delay: {elapsed*1000:.1f}ms ✓")

    # Measure rx_guard (now just fixed delay)
    start = time.time()
    is_clear = CollisionAvoidance.rx_guard(None, guard_time_ms=30)
    elapsed = time.time() - start

    assert is_clear is True, "Should always return True (RSSI check disabled)"
    assert 0.025 <= elapsed <= 0.040, f"Guard should be ~30ms, got {elapsed*1000:.1f}ms"
    print(f"  Guard delay: {elapsed*1000:.1f}ms ✓")

    print("  ✓ Collision avoidance timing working correctly")
    return True


def test_multi_packet_forwarding():
    """Test: Repeater forwards multi-packet sequences"""
    print("\nTesting: Multi-packet forwarding...")

    # Create 3-packet sequence
    packets = []
    for i in range(3):
        packet = LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=1,
            dest_node=102,
            payload=f"Student{i+1}|3rd|83".encode(),
            sequence_num=600 + i,
            ttl=3,
            multi_part_index=i,
            multi_part_total=3
        )
        packets.append(packet)

    print(f"  Created {len(packets)}-packet sequence")

    # Repeater forwards all 3
    forwarded = []
    for i, pkt in enumerate(packets):
        should_process, _ = pkt.should_process(200, NodeType.REPEATER, set())
        assert should_process, f"Packet {i+1} should be processed"

        repeated = pkt.create_repeat(200)
        assert repeated.multi_part_index == i, f"Index should be preserved: {i}"
        assert repeated.multi_part_total == 3, "Total should be preserved: 3"
        assert repeated.sender_node == 200, "Sender should be repeater"
        forwarded.append(repeated)

    print(f"  All {len(forwarded)} packets forwarded with preserved multi-packet info ✓")

    # Verify scanner can receive all
    for i, pkt in enumerate(forwarded):
        should_process, _ = pkt.should_process(102, NodeType.SCANNER, set())
        assert should_process, f"Scanner should accept packet {i+1}"

    print("  ✓ Multi-packet sequence forwarded correctly")
    return True


def main():
    """Run all E2E repeater tests"""
    print("=" * 60)
    print("END-TO-END REPEATER TESTS")
    print("=" * 60)
    print()

    tests = [
        test_scanner_to_server_via_repeater,
        test_server_to_scanner_via_repeater,
        test_multi_hop_chain,
        test_duplicate_detection,
        test_ttl_expiration,
        test_loop_detection,
        test_collision_avoidance_delay,
        test_multi_packet_forwarding,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            if result:
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

    if failed == 0:
        print("\n✅ All E2E repeater tests passed!")
        print("\nKey features verified:")
        print("  • Packet forwarding in both directions")
        print("  • Multi-hop chains (up to TTL limit)")
        print("  • Duplicate detection prevents re-forwarding")
        print("  • TTL expiration prevents infinite loops")
        print("  • Loop detection (own packet rejection)")
        print("  • Collision avoidance delays applied")
        print("  • Multi-packet sequences preserved")
        print("\nRepeater is ready for hardware testing!")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
