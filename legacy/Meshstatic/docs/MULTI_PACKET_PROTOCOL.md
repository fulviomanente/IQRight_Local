# Multi-Packet Protocol Documentation

## Overview

The IQRight Meshtastic system uses a multi-packet protocol to reliably send student information from server to scanner clients. This protocol addresses SX1262 HAT limitations with large packets by splitting data into smaller messages with sequencing.

## Problem Statement

The SX1262 LoRa HAT tends to lose packets when messages are too large. Instead of sending all student information in one large packet, we split it into multiple smaller packets with a counter to track delivery.

## Protocol Specification

### Message Format

All messages follow this pipe-delimited format:

```
name|grade_initial|msg_num/total_msgs
```

**Fields:**
- `name`: Student full name (e.g., "John Smith")
- `grade_initial`: First letter of grade (e.g., "5" for 5th grade, "K" for Kindergarten)
- `msg_num/total_msgs`: Packet counter (e.g., "1/3" means packet 1 of 3 total)

### Examples

**Single packet (complete data in one message):**
```
John Smith|5|1/1
```

**Multi-packet sequence (3 packets):**
```
Packet 1: John Smith|5|1/3
Packet 2: Maria Garcia|2|2/3
Packet 3: David Lee|K|3/3
```

### Command Messages

Commands use a different format:
```
cmd|ack|command_name
```

Example:
```
cmd|ack|cleanup
cmd|ack|break
cmd|ack|release
```

## Flow Diagram

### Single Packet Flow

```
Scanner sends QR code
    ↓
Server looks up student
    ↓
Server sends: "John Smith|5|1/1"
    ↓
Scanner displays:
  - Name: "John Smith"
  - Status: "Queue Confirmed" (green)
  - Adds to spreadsheet
```

### Multi-Packet Flow

```
Scanner sends QR code
    ↓
Server looks up student (finds 3 matches)
    ↓
Server sends packet 1/3: "John Smith|5|1/3"
    ↓
Scanner displays:
  - Name: "John Smith"
  - Status: "Receiving... (1/3)" (yellow)
    ↓
    ↓ (0.3s delay)
    ↓
Server sends packet 2/3: "Maria Garcia|2|2/3"
    ↓
Scanner displays:
  - Name: "John Smith" (unchanged)
  - Status: "Receiving... (2/3)" (yellow)
    ↓
    ↓ (0.3s delay)
    ↓
Server sends packet 3/3: "David Lee|K|3/3"
    ↓
Scanner displays:
  - Name: "John Smith" (from first packet)
  - Status: "Queue Confirmed" (green)
  - Adds "John Smith|5|" to spreadsheet
  - Resets counters
```

## Implementation Details

### Server Side (CaptureMeshstatic.py)

**Key Function**: `sendDataScanner(payload, destination_node, message_num, total_messages)`

```python
def sendDataScanner(payload: dict, destination_node: int,
                   message_num: int = 1, total_messages: int = 1):
    """
    Send data with multi-packet protocol

    Args:
        payload: Student data dict with 'name', 'hierarchyLevel2', etc.
        destination_node: Scanner node ID
        message_num: Current packet number (1-indexed)
        total_messages: Total packets in sequence
    """
    if 'name' in payload:
        grade_initial = getGrade(payload['hierarchyLevel2'])[:1]
        msg = f"{payload['name']}|{grade_initial}|{message_num}/{total_messages}"
    else:
        msg = f"cmd|ack|{payload['command']}"

    mesh_interface.sendText(
        text=msg,
        destinationId=destination_node,
        wantAck=True
    )
```

**Sending Multiple Results:**

```python
if isinstance(payload, list):
    total_messages = len(payload)
    for idx, item in enumerate(payload, start=1):
        time.sleep(0.3)  # Delay between packets
        sendDataScanner(item, source_node,
                       message_num=idx,
                       total_messages=total_messages)
```

### Client Side (scanner_meshstatic.py)

**State Tracking Variables:**

```python
self.expected_message_count = 0  # Total packets expected
self.received_message_count = 0  # Packets received so far
self.current_student_name = ""   # Name from first packet
self.current_grade = ""          # Grade from first packet
```

**Processing Logic:**

```python
def processResponse(self, response: str):
    parts = response.split("|")
    name = parts[0]
    grade_initial = parts[1]
    current_msg, total_msgs = parts[2].split('/')
    current_msg = int(current_msg)
    total_msgs = int(total_msgs)

    if current_msg == 1:
        # First packet - initialize
        self.expected_message_count = total_msgs
        self.received_message_count = 1
        self.current_student_name = name
        self.current_grade = grade_initial

        if total_msgs > 1:
            self.lbl_status.config(text=f"Receiving... ({current_msg}/{total_msgs})",
                                  bg="yellow")
        else:
            # Single packet - done!
            self.lbl_status.config(text="Queue Confirmed", bg="green")
            self.sheet.insert_row([name, grade_initial, ""], redraw=True)

    elif current_msg == total_msgs:
        # Last packet - complete!
        self.lbl_status.config(text="Queue Confirmed", bg="green")
        self.sheet.insert_row([self.current_student_name,
                              self.current_grade, ""], redraw=True)

    else:
        # Middle packet - update status
        self.lbl_status.config(text=f"Receiving... ({current_msg}/{total_msgs})",
                              bg="yellow")
```

## Status Display States

| State | Label Color | Meaning |
|-------|-------------|---------|
| `Idle` | Blue | Waiting for scan |
| `Sending to IQRight Server` | Blue | QR code sent to server |
| `Receiving... (1/3)` | Yellow | Receiving multi-packet response |
| `Receiving... (2/3)` | Yellow | Still receiving... |
| `Queue Confirmed` | Green | All packets received, added to queue |
| `Duplicate QRCode` | Orange | Code already scanned |
| `Error: ...` | Red | Error occurred |

## Timing Considerations

### Server Timing

- **Delay between packets**: 0.3 seconds (`time.sleep(0.3)`)
- **Total send time for 3 packets**: ~0.9 seconds
- **Total send time for 5 packets**: ~1.5 seconds

### Scanner Timing

- **Packet 1 arrives**: Instantly (once Meshtastic delivers)
- **Status changes**: Immediate (GUI update on main thread)
- **Packet 2 arrives**: ~0.3-0.4 seconds after Packet 1
- **Final confirmation**: When last packet arrives

### Expected Latencies

| Packets | Server Send Time | Mesh Delivery | Total Latency |
|---------|------------------|---------------|---------------|
| 1 | 0s | ~0.5s | ~0.5s |
| 2 | 0.3s | ~0.5s | ~0.8s |
| 3 | 0.6s | ~0.5s | ~1.1s |
| 5 | 1.2s | ~0.5s | ~1.7s |

## Error Handling

### Missing Packet

If a packet is lost in transmission:

**Scenario**: Server sends 1/3, 2/3, 3/3 but client only receives 1/3 and 3/3

**Behavior**:
- Client receives 1/3: Sets `expected_message_count = 3`, status = "Receiving... (1/3)"
- Client receives 3/3: Checks `current_msg (3) == total_msgs (3)`, completes!
- **Result**: Client completes successfully (uses data from first packet)

**Trade-off**: Scanner only displays data from FIRST packet. Additional packets in multi-packet sequences are currently informational.

### Out-of-Order Packets

**Scenario**: Packets arrive as 1/3, 3/3, 2/3

**Behavior**:
- Client receives 1/3: Initializes, status = "Receiving... (1/3)"
- Client receives 3/3: `current_msg (3) == total_msgs (3)` → Completes early!
- Client receives 2/3: Already completed, will process but won't change display

**Protection**: Client only adds to spreadsheet once (when last packet detected)

### Timeout

Currently, there's **no explicit timeout** on multi-packet reception.

**Recommendation**: Add timeout logic:

```python
# In __init__:
self.multi_packet_timeout_id = None

# When receiving first packet:
if current_msg == 1 and total_msgs > 1:
    # Cancel any existing timeout
    if self.multi_packet_timeout_id:
        self.after_cancel(self.multi_packet_timeout_id)

    # Set 10-second timeout
    self.multi_packet_timeout_id = self.after(10000, self.handle_multipacket_timeout)

# When receiving last packet:
if current_msg == total_msgs:
    # Cancel timeout
    if self.multi_packet_timeout_id:
        self.after_cancel(self.multi_packet_timeout_id)
        self.multi_packet_timeout_id = None
```

## Testing

### Test Case 1: Single Packet

**Setup**: Student with one record in database

**Expected**:
1. Server sends: `"John Smith|5|1/1"`
2. Scanner displays: "Queue Confirmed" (green)
3. Spreadsheet shows: "John Smith | 5 | "

### Test Case 2: Multi-Packet (3 packets)

**Setup**: Student with 3 records in database

**Expected**:
1. Server sends: `"John Smith|5|1/3"`
   - Scanner: "Receiving... (1/3)" (yellow)
2. Server sends: `"John Smith Jr|6|2/3"` (0.3s later)
   - Scanner: "Receiving... (2/3)" (yellow)
3. Server sends: `"Johnathan Smith|7|3/3"` (0.6s later)
   - Scanner: "Queue Confirmed" (green)
   - Spreadsheet: "John Smith | 5 | "

### Test Case 3: Rapid Scanning

**Setup**: Scan two different QR codes quickly

**Expected**:
1. QR Code A scanned → Server sends 1/3
   - Scanner: "Receiving... (1/3)"
2. Server sends 2/3
   - Scanner: "Receiving... (2/3)"
3. QR Code B scanned → Server sends 1/1 (different student)
   - Scanner: Gets mixed packets!

**Issue**: Need to track per-QR-code sequence

**Solution**: Wait for `response_received.set()` before allowing next scan

## Future Enhancements

### 1. Full Data in Multi-Packet

Currently only first packet data is displayed. Could accumulate:

```python
self.pending_students = []  # List of all students in sequence

# On each packet:
self.pending_students.append({'name': name, 'grade': grade_initial})

# On last packet:
for student in self.pending_students:
    self.sheet.insert_row([student['name'], student['grade'], ""])
```

### 2. Timeout Detection

Add explicit timeout handling (see Timeout section above)

### 3. Retry on Missing Packets

Server could implement retry logic if ACK not received

### 4. Packet Sequence ID

Add unique sequence ID to distinguish between different scans:

```
name|grade|msg_num/total_msgs|sequence_id
John Smith|5|1/3|XY123
```

## Logging Examples

### Server Logs

```
INFO - Received from node 102: 102|P18710587|1
INFO - Using API results
INFO - Sent packet 1/3: {"name":"John Smith",...}
INFO - Packet 1/3 sent to node 102
INFO - Sent packet 2/3: {"name":"Maria Garcia",...}
INFO - Packet 2/3 sent to node 102
INFO - Sent packet 3/3: {"name":"David Lee",...}
INFO - Packet 3/3 sent to node 102
```

### Scanner Logs

```
INFO - Received from node 1: John Smith|5|1/3
INFO - Received packet 1/3: John Smith, Grade: 5
INFO - Expecting 3 total messages, received 1
INFO - Received from node 1: Maria Garcia|2|2/3
INFO - Received packet 2/3: Maria Garcia, Grade: 2
INFO - Received 2/3 packets
INFO - Received from node 1: David Lee|K|3/3
INFO - Received packet 3/3: David Lee, Grade: K
INFO - All 3 packets received successfully
```

## Summary

The multi-packet protocol provides:
- ✅ **Reliable delivery** of student data despite packet size limitations
- ✅ **Visual feedback** with "Receiving..." status
- ✅ **Progress tracking** with current/total counter
- ✅ **Graceful degradation** if packets are lost
- ✅ **Simple implementation** with clear state management

The protocol successfully addresses the 10-second delay issue by:
1. Not relying on Meshtastic power-saving timing
2. Providing explicit sequencing information
3. Giving immediate feedback on multi-packet transfers
