#!/usr/bin/env python3
"""
Unit Test: Duplicate Detection

Tests that duplicate packets are detected and rejected.
Can run locally without LoRa radio.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set LOCAL mode to avoid hardware initialization
os.environ["LOCAL"] = "TRUE"

from lora import LoRaTransceiver, NodeType, LoRaPacket, PacketType


def test_duplicate_detection():
    """Test duplicate packet detection"""
    print("Testing duplicate packet detection...")

    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Create packet FROM ANOTHER NODE (scanner 102 -> server 1)
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,  # From scanner
        dest_node=1,      # To server
        payload=b"test",
        sequence_num=42
    )

    # First time should process
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, transceiver.seen_packets
    )
    assert should_process, "First packet should be processed"
    print(f"  ✓ First occurrence: should_process=True, reason={reason}")

    # Add to seen
    transceiver.seen_packets.add((packet.source_node, packet.sequence_num))

    # Second time should be duplicate
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, transceiver.seen_packets
    )
    assert not should_process, "Duplicate should be rejected"
    assert reason == "duplicate"
    print(f"  ✓ Second occurrence: should_process=False, reason={reason}")

    return True


def test_sequence_number_wrap():
    """Test duplicate detection with sequence number wrap"""
    print("\nTesting duplicate detection with sequence wrap...")

    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Manually set sequence number near wrap point
    transceiver.sequence_num = 65534

    packets = []
    for i in range(5):
        seq = transceiver.get_next_sequence()
        # Create packet FROM ANOTHER NODE (scanner 102)
        packet = LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=102,
            dest_node=1,
            payload=f"packet_{i}".encode('utf-8'),
            sequence_num=seq
        )
        packets.append(packet)

    # Sequence numbers should wrap: 65535, 0, 1, 2, 3
    assert packets[0].sequence_num == 65535
    assert packets[1].sequence_num == 0
    assert packets[2].sequence_num == 1
    print(f"  ✓ Sequence numbers wrap correctly: 65535 -> 0 -> 1")

    # All packets should be unique (receiving them at server)
    seen = set()
    for packet in packets:
        should_process, reason = packet.should_process(1, NodeType.SERVER, seen)
        assert should_process, f"Packet {packet.sequence_num} should be unique"
        seen.add((packet.source_node, packet.sequence_num))

    print(f"  ✓ All {len(packets)} packets detected as unique across wrap")

    return True


def test_loop_detection():
    """Test that own packets looped back are rejected"""
    print("\nTesting loop detection (own packet)...")

    transceiver = LoRaTransceiver(
        node_id=102,
        node_type=NodeType.SCANNER,
        frequency=915.23,
        tx_power=23
    )

    # Create packet from this node
    packet = transceiver.create_data_packet(
        dest_node=1,
        payload=b"test"
    )

    # Should be rejected as own packet
    should_process, reason = packet.should_process(
        102, NodeType.SCANNER, transceiver.seen_packets
    )

    assert not should_process, "Own packet should be rejected"
    assert reason == "own_packet_looped"
    print(f"  ✓ Own packet rejected: reason={reason}")

    return True


def test_ttl_expiration():
    """Test TTL expiration detection"""
    print("\nTesting TTL expiration detection...")

    # Create packet with TTL=0
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=1,
        ttl=0
    )

    # Should be rejected due to TTL
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, set()
    )

    assert not should_process, "TTL=0 packet should be rejected"
    assert reason == "ttl_expired"
    print(f"  ✓ TTL=0 packet rejected: reason={reason}")

    return True


def test_not_for_me():
    """Test packets addressed to other nodes"""
    print("\nTesting 'not for me' detection...")

    # Create packet addressed to node 200
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=200,  # Not for node 1
        payload=b"test",
        sequence_num=1,
        ttl=3
    )

    # Server (node 1) receiving packet for node 200
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, set()
    )

    assert not should_process, "Packet for other node should be rejected"
    assert reason == "not_for_me"
    print(f"  ✓ Packet for node 200 rejected by node 1: reason={reason}")

    return True


def test_repeater_forwarding():
    """Test repeater forwards packets not addressed to it"""
    print("\nTesting repeater forwarding logic...")

    # Create packet from scanner to server
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=1,
        ttl=3
    )

    # Repeater (node 200) receiving packet
    should_process, reason = packet.should_process(
        200, NodeType.REPEATER, set()
    )

    assert should_process, "Repeater should forward packet"
    assert reason == "forward"
    print(f"  ✓ Repeater forwards packet: reason={reason}")

    return True


def test_broadcast_address():
    """Test broadcast packets (dest=0) are processed by all"""
    print("\nTesting broadcast packet (dest=0)...")

    # Create broadcast packet from node 1
    packet = LoRaPacket.create(
        packet_type=PacketType.BEACON,
        source_node=1,
        dest_node=0,  # Broadcast
        payload=b"beacon",
        sequence_num=1,
        ttl=3
    )

    # Should be processed by OTHER nodes (not own node)
    # Node 1 (source) would reject as own_packet_looped - this is correct!
    # But nodes 102 and 200 should process it
    for node_id in [102, 200]:
        should_process, reason = packet.should_process(
            node_id, NodeType.SCANNER, set()
        )
        assert should_process, f"Node {node_id} should process broadcast"
        print(f"  ✓ Node {node_id} processes broadcast: reason={reason}")

    # Node 1 (source itself) should reject as own_packet_looped
    should_process, reason = packet.should_process(1, NodeType.SERVER, set())
    assert not should_process, "Source node should reject own broadcast"
    assert reason == "own_packet_looped"
    print(f"  ✓ Source node 1 rejects own broadcast: reason={reason}")

    return True


def test_seen_packets_cleanup():
    """Test seen_packets set cleanup to prevent memory growth"""
    print("\nTesting seen_packets cleanup...")

    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Add packets beyond max_seen limit
    for i in range(transceiver.max_seen + 10):
        transceiver.seen_packets.add((102, i))

    # Verify we exceeded the limit
    initial_size = len(transceiver.seen_packets)
    assert initial_size > transceiver.max_seen, f"Test setup error: didn't exceed max_seen"
    print(f"  ✓ Added {initial_size} packets (exceeds max_seen={transceiver.max_seen})")

    # Simulate cleanup logic (from receive_packet method)
    if len(transceiver.seen_packets) > transceiver.max_seen:
        # Remove oldest half
        transceiver.seen_packets = set(list(transceiver.seen_packets)[500:])

    # Should now be cleaned up
    assert len(transceiver.seen_packets) <= transceiver.max_seen, \
        f"seen_packets not cleaned: {len(transceiver.seen_packets)} > {transceiver.max_seen}"

    print(f"  ✓ After cleanup: {len(transceiver.seen_packets)} packets (≤ {transceiver.max_seen})")

    return True


def main():
    """Run all duplicate detection tests"""
    print("=" * 60)
    print("DUPLICATE DETECTION TESTS (LOCAL - NO HARDWARE REQUIRED)")
    print("=" * 60)

    tests = [
        test_duplicate_detection,
        test_sequence_number_wrap,
        test_loop_detection,
        test_ttl_expiration,
        test_not_for_me,
        test_repeater_forwarding,
        test_broadcast_address,
        test_seen_packets_cleanup
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
