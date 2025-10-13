I'm# LoRa Packet Protocol Testing Guide

This document provides comprehensive testing procedures for the enhanced LoRa packet protocol with binary serialization, CRC validation, collision avoidance, and repeater support.

## Table of Contents

1. [Test Environment Setup](#test-environment-setup)
2. [Unit Tests](#unit-tests)
3. [Integration Tests](#integration-tests)
4. [End-to-End Tests](#end-to-end-tests)
5. [Performance Tests](#performance-tests)
6. [Troubleshooting](#troubleshooting)

---

## Test Environment Setup

### Hardware Requirements

- **Server**: 1x Raspberry Pi with RFM95x LoRa module (Node ID: 1)
- **Scanner**: 1-2x Raspberry Pi with RFM95x and QR scanner (Node ID: 102, 103)
- **Repeater** (optional): 1x Raspberry Pi Zero with RFM95x (Node ID: 200)

### Software Requirements

```bash
# Install dependencies
pip install adafruit-circuitpython-rfm9x
pip install python-dotenv
```

### Configuration

Set environment variables for each node:

**Server (.env)**:
```bash
LORA_NODE_TYPE=SERVER
LORA_NODE_ID=1
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_ENABLE_CA=TRUE
DEBUG=TRUE
```

**Scanner (.env)**:
```bash
LORA_NODE_TYPE=SCANNER
LORA_NODE_ID=102
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_ENABLE_CA=TRUE
DEBUG=TRUE
```

**Repeater (.env)**:
```bash
LORA_NODE_TYPE=REPEATER
LORA_NODE_ID=200
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_ENABLE_CA=TRUE
DEBUG=TRUE
```

---

## Unit Tests

### 1. Packet Serialization/Deserialization

Test that packets can be serialized and deserialized correctly.

```python
# test_packet_serialization.py
from lora import LoRaPacket, PacketType, MultiPartFlags

def test_packet_roundtrip():
    """Test packet serialization and deserialization"""
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
    print(f"Serialized size: {len(data)} bytes")

    # Deserialize
    reconstructed = LoRaPacket.deserialize(data)

    # Validate
    assert reconstructed is not None, "Deserialization failed"
    assert reconstructed.source_node == 102
    assert reconstructed.dest_node == 1
    assert reconstructed.sequence_num == 42
    assert reconstructed.ttl == 3
    assert reconstructed.payload == b"102|123456789|1"

    print("✓ Packet roundtrip test passed")

if __name__ == "__main__":
    test_packet_roundtrip()
```

### 2. CRC Validation

Test that CRC detects corrupted packets.

```python
# test_crc_validation.py
from lora import LoRaPacket, PacketType

def test_crc_validation():
    """Test CRC detects corrupted packets"""
    # Create packet
    packet = LoRaPacket.create(
        packet_type=PacketType.DATA,
        source_node=102,
        dest_node=1,
        payload=b"test",
        sequence_num=1
    )

    data = packet.serialize()

    # Corrupt a byte in the payload
    corrupted = bytearray(data)
    corrupted[25] ^= 0xFF  # Flip bits in payload

    # Try to deserialize
    result = LoRaPacket.deserialize(bytes(corrupted))

    assert result is None, "CRC should have detected corruption"
    print("✓ CRC validation test passed")

if __name__ == "__main__":
    test_crc_validation()
```

### 3. Multi-Packet Flags

Test multi-packet sequence flag handling.

```python
# test_multi_packet.py
from lora import LoRaPacket, PacketType, MultiPartFlags

def test_multi_packet_flags():
    """Test multi-packet sequence flags"""
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

    assert first.is_multi_part()
    assert first.multi_part_index == 1
    assert first.multi_part_total == 3

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

    assert middle.is_multi_part()

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

    assert last.is_multi_part()
    assert last.multi_flags & MultiPartFlags.LAST

    print("✓ Multi-packet flags test passed")

if __name__ == "__main__":
    test_multi_packet_flags()
```

### 4. Duplicate Detection

Test that duplicate packets are detected.

```python
# test_duplicate_detection.py
from lora import LoRaTransceiver, NodeType

def test_duplicate_detection():
    """Test duplicate packet detection"""
    transceiver = LoRaTransceiver(
        node_id=1,
        node_type=NodeType.SERVER,
        frequency=915.23,
        tx_power=23
    )

    # Create packet
    packet = transceiver.create_data_packet(
        dest_node=102,
        payload=b"test"
    )

    # First time should process
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, transceiver.seen_packets
    )
    assert should_process, "First packet should be processed"

    # Add to seen
    transceiver.seen_packets.add((packet.source_node, packet.sequence_num))

    # Second time should be duplicate
    should_process, reason = packet.should_process(
        1, NodeType.SERVER, transceiver.seen_packets
    )
    assert not should_process, "Duplicate should be rejected"
    assert reason == "duplicate"

    print("✓ Duplicate detection test passed")

if __name__ == "__main__":
    test_duplicate_detection()
```

---

## Integration Tests

### Test 1: Server ↔ Scanner Communication

Test basic communication between server and scanner.

**Steps:**
1. Start server: `LOCAL=TRUE python CaptureLora.py`
2. Start scanner: `python scanner_queue.py`
3. Scan a QR code on the scanner
4. Verify server receives request and sends response
5. Verify scanner displays student info

**Expected Results:**
- Server log shows: `Received LoRaPacket(type=DATA, src=102, dst=1, ...)`
- Server log shows: `Sent to scanner 102: Name|Grade|Teacher [1/1]`
- Scanner displays student information

### Test 2: Multi-Packet Response

Test server sending multiple student records.

**Steps:**
1. Modify test to return multiple students with same QR code
2. Scan QR code on scanner
3. Verify all packets are received and displayed

**Expected Results:**
- Server sends multiple packets with proper index/total
- Scanner receives all packets in sequence
- Scanner displays all students

### Test 3: Command Acknowledgment

Test command flow (break, release, undo, cleanup).

**Steps:**
1. Start server and scanner
2. Press "Break" button on scanner
3. Verify server receives command
4. Verify scanner receives ACK

**Expected Results:**
- Server log shows: `Received LoRaPacket(type=CMD, ...)`
- Scanner log shows: `SERVER ACK TRUE`
- Scanner displays "CMD Confirmed"

### Test 4: Collision Avoidance

Test collision avoidance with multiple scanners.

**Steps:**
1. Start server
2. Start 2 scanners (node 102 and 103)
3. Scan QR codes on both scanners simultaneously
4. Verify both requests are processed

**Expected Results:**
- Both scanners receive responses
- Server log shows randomized delays and channel sensing
- No packet collisions or lost messages

---

## End-to-End Tests

### Test 1: Server + Scanner + Repeater

Test full mesh network with repeater.

**Setup:**
- Place server and scanner far apart (outside LoRa range)
- Place repeater between them

**Steps:**
1. Start server: `python CaptureLora.py`
2. Start repeater: `LORA_NODE_ID=200 python repeater.py`
3. Start scanner: `python scanner_queue.py`
4. Scan QR code
5. Verify packet flows through repeater

**Expected Results:**
- Scanner sends packet (src=102, sender=102, TTL=3)
- Repeater receives and forwards (src=102, sender=200, TTL=2)
- Server receives packet with correct TTL
- Server response flows back through repeater
- Scanner displays student info

**Verify in logs:**
- Repeater log: `Forwarding packet: LoRaPacket(src=102, sender=200, ttl=2)`
- Server log: `Received LoRaPacket(src=102, sender=200, ttl=2)`

### Test 2: TTL Expiration

Test that packets with TTL=0 are dropped.

**Setup:**
- Set LORA_TTL=1 for scanner

**Steps:**
1. Start server and repeater
2. Start scanner with TTL=1
3. Scan QR code
4. Verify repeater drops packet with TTL=0

**Expected Results:**
- Scanner sends packet with TTL=1
- Repeater receives, decrements to TTL=0
- Repeater drops packet: "Dropped TTL expired packet"

### Test 3: Loop Prevention

Test that packets don't loop infinitely.

**Setup:**
- 2 repeaters in a loop configuration

**Steps:**
1. Start server, repeater 200, repeater 201
2. Send test packet from server
3. Verify repeaters don't infinitely forward

**Expected Results:**
- Each repeater forwards packet once
- Duplicate detection prevents re-forwarding
- No infinite loop

---

## Performance Tests

### Test 1: Throughput

Measure packets per second.

```python
# test_throughput.py
import time
from lora import LoRaTransceiver, NodeType

def test_throughput():
    transceiver = LoRaTransceiver(
        node_id=102,
        node_type=NodeType.SCANNER,
        frequency=915.23,
        tx_power=23
    )

    num_packets = 100
    start_time = time.time()

    for i in range(num_packets):
        packet = transceiver.create_data_packet(
            dest_node=1,
            payload=f"Packet {i}".encode('utf-8')
        )
        transceiver.send_packet(packet, use_ack=False)

    elapsed = time.time() - start_time
    throughput = num_packets / elapsed

    print(f"Throughput: {throughput:.2f} packets/sec")
    print(f"Average time per packet: {elapsed/num_packets*1000:.1f}ms")

if __name__ == "__main__":
    test_throughput()
```

**Expected:** ~2-5 packets/sec (with ACK), ~10-20 packets/sec (without ACK)

### Test 2: Range Test

Measure maximum communication range.

**Steps:**
1. Start server
2. Walk away with scanner, testing at intervals
3. Record maximum distance where communication works

**Expected:** ~1-2km line-of-sight, ~200-500m with obstacles

### Test 3: Collision Rate

Measure collision rate with multiple scanners.

**Steps:**
1. Start server
2. Start 3+ scanners
3. Scan QR codes on all scanners simultaneously
4. Count successful vs failed transmissions

**Expected:** >95% success rate with collision avoidance enabled

---

## Troubleshooting

### Problem: CRC Errors

**Symptoms:** Server logs show "CRC mismatch"

**Possible Causes:**
- Radio interference
- Incorrect frequency setting
- Hardware malfunction

**Solutions:**
1. Check frequency matches on all nodes
2. Move away from interference sources (WiFi, etc)
3. Reduce TX power to avoid overload
4. Check hardware connections

### Problem: Packets Not Received

**Symptoms:** Scanner sends but server doesn't receive

**Possible Causes:**
- Out of range
- Wrong node ID configuration
- Hardware not initialized

**Solutions:**
1. Check logs for "LoRa initialized" message
2. Verify node IDs in config
3. Check distance between nodes
4. Verify frequency and TX power settings

### Problem: Duplicate Detection Issues

**Symptoms:** Valid packets rejected as duplicates

**Possible Causes:**
- Sequence number not incrementing
- seen_packets set not cleared

**Solutions:**
1. Check `get_next_sequence()` is called
2. Restart nodes to clear seen_packets
3. Reduce max_seen if memory constrained

### Problem: Repeater Not Forwarding

**Symptoms:** Repeater receives but doesn't forward

**Possible Causes:**
- TTL=0
- Collision avoidance failing
- Wrong node ID range

**Solutions:**
1. Check LORA_NODE_ID is 200-256
2. Check TTL > 0 in received packets
3. Verify collision avoidance not blocking sends
4. Check repeater logs for error messages

### Problem: Multi-Packet Sequence Incomplete

**Symptoms:** Scanner displays only partial student list

**Possible Causes:**
- Packet loss
- Timeout too short
- Server not sending all packets

**Solutions:**
1. Increase timeout in scanner
2. Check server logs for send failures
3. Reduce distance or add repeater
4. Enable collision avoidance

---

## Validation Checklist

Before deploying to production, verify:

- [ ] All unit tests pass
- [ ] Server receives and processes scanner requests
- [ ] Scanner receives and displays server responses
- [ ] Multi-packet sequences work correctly
- [ ] Commands (break, release, undo) are acknowledged
- [ ] Collision avoidance reduces collisions
- [ ] Repeater forwards packets and updates TTL
- [ ] Duplicate packets are rejected
- [ ] CRC detects corrupted packets
- [ ] TTL prevents infinite loops
- [ ] Performance meets requirements (range, throughput)
- [ ] All logs show proper packet structure
- [ ] No crashes or errors under load

---

## Next Steps

After successful testing:

1. Deploy to production environment
2. Monitor repeater statistics
3. Tune collision avoidance parameters if needed
4. Document any environment-specific settings
5. Create deployment runbook
