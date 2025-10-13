#!/usr/bin/env python3
"""
Unit Test: Multi-Packet Sequences

Tests multi-packet protocol with FIRST/MORE/LAST flags.
Can run locally without LoRa radio.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lora import LoRaPacket, PacketType, MultiPartFlags


def test_multi_packet_flags():
    """Test multi-packet sequence flags"""
    print("Testing multi-packet sequence flags...")

    # First packet
    first = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"Student 1",
        sequence_num=1,
        multi_flags=MultiPartFlags.FIRST | MultiPartFlags.MORE,
        multi_part_index=1,
        multi_part_total=3
    )

    assert first.is_multi_part(), "First packet should be multi-part"
    assert first.multi_part_index == 1, "First index should be 1"
    assert first.multi_part_total == 3, "Total should be 3"
    assert first.multi_flags & MultiPartFlags.FIRST, "Should have FIRST flag"
    assert first.multi_flags & MultiPartFlags.MORE, "Should have MORE flag"
    print(f"  ✓ First packet: index={first.multi_part_index}/{first.multi_part_total}")

    # Middle packet
    middle = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"Student 2",
        sequence_num=2,
        multi_flags=MultiPartFlags.MORE,
        multi_part_index=2,
        multi_part_total=3
    )

    assert middle.is_multi_part(), "Middle packet should be multi-part"
    assert middle.multi_flags & MultiPartFlags.MORE, "Should have MORE flag"
    print(f"  ✓ Middle packet: index={middle.multi_part_index}/{middle.multi_part_total}")

    # Last packet
    last = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"Student 3",
        sequence_num=3,
        multi_flags=MultiPartFlags.LAST,
        multi_part_index=3,
        multi_part_total=3
    )

    assert last.is_multi_part(), "Last packet should be multi-part"
    assert last.multi_flags & MultiPartFlags.LAST, "Should have LAST flag"
    assert not (last.multi_flags & MultiPartFlags.MORE), "Should NOT have MORE flag"
    print(f"  ✓ Last packet: index={last.multi_part_index}/{last.multi_part_total}")

    return True


def test_single_packet():
    """Test single packet (not part of sequence)"""
    print("\nTesting single packet (ONLY flag)...")

    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=1,
        dest_node=102,
        payload=b"Single student",
        sequence_num=1,
        multi_flags=MultiPartFlags.ONLY
    )

    assert not packet.is_multi_part(), "ONLY packet should not be multi-part"
    assert packet.multi_flags == MultiPartFlags.ONLY, "Should have ONLY flag"
    print(f"  ✓ Single packet correctly marked with ONLY flag")

    return True


def test_multi_packet_serialization():
    """Test multi-packet serialization/deserialization"""
    print("\nTesting multi-packet serialization...")

    packets = []
    total = 5

    for i in range(1, total + 1):
        # Determine flags
        if i == 1:
            flags = MultiPartFlags.FIRST | MultiPartFlags.MORE
        elif i == total:
            flags = MultiPartFlags.LAST
        else:
            flags = MultiPartFlags.MORE

        packet = LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=1,
            dest_node=102,
            payload=f"Packet {i} of {total}".encode('utf-8'),
            sequence_num=i,
            multi_flags=flags,
            multi_part_index=i,
            multi_part_total=total
        )

        packets.append(packet)

    # Serialize and deserialize all packets
    for i, packet in enumerate(packets, 1):
        data = packet.serialize()
        reconstructed = LoRaPacket.deserialize(data)

        assert reconstructed is not None, f"Packet {i} deserialization failed"
        assert reconstructed.multi_part_index == i, f"Index mismatch for packet {i}"
        assert reconstructed.multi_part_total == total, f"Total mismatch for packet {i}"

    print(f"  ✓ All {total} packets serialized/deserialized correctly")
    return True


def test_multi_packet_sequence_validation():
    """Test validation logic for multi-packet sequences"""
    print("\nTesting multi-packet sequence validation...")

    # Create a 3-packet sequence
    packets = []
    for i in range(1, 4):
        if i == 1:
            flags = MultiPartFlags.FIRST | MultiPartFlags.MORE
        elif i == 3:
            flags = MultiPartFlags.LAST
        else:
            flags = MultiPartFlags.MORE

        packet = LoRaPacket.create(
            packet_type=PacketType.DATA,
            source_node=1,
            dest_node=102,
            payload=f"Data {i}".encode('utf-8'),
            sequence_num=i,
            multi_flags=flags,
            multi_part_index=i,
            multi_part_total=3
        )
        packets.append(packet)

    # Validate first packet
    assert packets[0].multi_flags & MultiPartFlags.FIRST
    assert packets[0].multi_flags & MultiPartFlags.MORE
    print(f"  ✓ First packet has FIRST+MORE flags")

    # Validate middle packet
    assert packets[1].multi_flags & MultiPartFlags.MORE
    assert not (packets[1].multi_flags & MultiPartFlags.FIRST)
    assert not (packets[1].multi_flags & MultiPartFlags.LAST)
    print(f"  ✓ Middle packet has only MORE flag")

    # Validate last packet
    assert packets[2].multi_flags & MultiPartFlags.LAST
    assert not (packets[2].multi_flags & MultiPartFlags.MORE)
    print(f"  ✓ Last packet has only LAST flag")

    return True


def test_transceiver_helper_single():
    """Test LoRaTransceiver helper for single packet"""
    print("\nTesting LoRaTransceiver helper for single packet...")

    # Set LOCAL mode to avoid hardware initialization
    os.environ["LOCAL"] = "TRUE"

    from lora import LoRaTransceiver, NodeType

    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Create single packet (multi_part_total=0)
    packet = transceiver.create_data_packet(
        dest_node=102,
        payload=b"Test data",
        multi_part_index=0,
        multi_part_total=0
    )

    assert not packet.is_multi_part(), "Should be single packet"
    assert packet.multi_flags == MultiPartFlags.ONLY
    print(f"  ✓ Single packet created with ONLY flag")

    return True


def test_transceiver_helper_multi():
    """Test LoRaTransceiver helper for multi-packet"""
    print("\nTesting LoRaTransceiver helper for multi-packet sequence...")

    os.environ["LOCAL"] = "TRUE"

    from lora import LoRaTransceiver, NodeType

    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Create 3-packet sequence
    total = 3
    packets = []

    for i in range(1, total + 1):
        packet = transceiver.create_data_packet(
            dest_node=102,
            payload=f"Packet {i}".encode('utf-8'),
            multi_part_index=i,
            multi_part_total=total
        )
        packets.append(packet)

    # Validate flags
    assert packets[0].multi_flags & MultiPartFlags.FIRST
    assert packets[0].multi_flags & MultiPartFlags.MORE
    print(f"  ✓ First packet: FIRST+MORE")

    assert packets[1].multi_flags & MultiPartFlags.MORE
    assert not (packets[1].multi_flags & MultiPartFlags.FIRST)
    assert not (packets[1].multi_flags & MultiPartFlags.LAST)
    print(f"  ✓ Middle packet: MORE only")

    assert packets[2].multi_flags & MultiPartFlags.LAST
    assert not (packets[2].multi_flags & MultiPartFlags.MORE)
    print(f"  ✓ Last packet: LAST only")

    return True


def main():
    """Run all multi-packet tests"""
    print("=" * 60)
    print("MULTI-PACKET TESTS (LOCAL - NO HARDWARE REQUIRED)")
    print("=" * 60)

    tests = [
        test_multi_packet_flags,
        test_single_packet,
        test_multi_packet_serialization,
        test_multi_packet_sequence_validation,
        test_transceiver_helper_single,
        test_transceiver_helper_multi
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
