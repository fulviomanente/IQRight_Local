# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status: MVP READY FOR GO-LIVE

**Last Updated**: 2025 (Pre E2E Testing)
**Status**: All core features implemented, ready for end-to-end testing and production deployment

---

## Overview and Project Structure

IQRight LoRa is a mesh network system for managing school pickup car lines. The system uses LoRa (Long Range) radio communication to enable scanners in the parking lot to communicate with a central server, even at extended distances, using repeater nodes.

### Architecture: Mesh Network

```
Server (Node 1) - Central Hub
  |
  ├── Scanner 102 (Gym Side) - Direct connection
  ├── Scanner 103 (East Side) - Direct connection
  └── Repeater 200
       ├── Scanner 104 (Far Location) - Via repeater
       └── Scanner 105 (Far Location) - Via repeater
```

**Node Types:**
- **Server** (Node ID: 1) - Central data processor and MQTT hub
- **Scanner** (Node ID: 100-199) - QR code readers operated by staff
- **Repeater** (Node ID: 200-256) - Range extenders for distant scanners

---

## Complete Implementation (Phase 2 - COMPLETED)

### ✅ Binary Packet Protocol (`lora/`)

**Status**: Fully implemented and tested (38/38 tests passing)

#### Packet Structure (22-byte header + variable payload)
- **Source Node** (1 byte) - Original sender
- **Destination Node** (1 byte) - Target recipient
- **Sender Node** (1 byte) - Last forwarder (for repeaters)
- **Packet Type** (1 byte) - DATA, ACK, CMD, HELLO, HELLO_ACK
- **Sequence Number** (2 bytes) - Duplicate detection (0-65535)
- **Timestamp** (4 bytes) - Creation time
- **TTL** (1 byte) - Hop limit (default: 3)
- **Flags** (1 byte) - ACK_REQ, IS_REPEAT
- **Multi-part Flags** (1 byte) - FIRST, MORE, LAST, ONLY
- **Multi-part Index/Total** (2 bytes) - Packet sequence
- **Payload Length** (2 bytes) - Data size
- **CRC16** (2 bytes) - Error detection
- **Reserved** (4 bytes) - Future use
- **Payload** (variable) - Actual data

#### Key Features
- **Binary serialization** using `struct.pack/unpack`
- **CRC16-CCITT** validation
- **Duplicate detection** via (source_node, sequence_num) tuples
- **Multi-packet support** for large responses (>240 bytes)
- **Sequence wrapping** (0-65535 with rollover)

**Files**:
- `lora/packet_handler.py` - Main packet creation/parsing (482 lines)
- `lora/node_types.py` - Enums and constants (39 lines)
- `lora/collision_avoidance.py` - TX optimization (108 lines)
- `lora/__init__.py` - Public API exports

### ✅ HELLO Handshake Protocol

**Status**: Fully implemented (scanner, server, repeater)

**Problem Solved**: When a scanner reboots, its sequence number resets to 0, but the server still tracks old sequences and rejects packets as duplicates.

**Solution**: HELLO handshake on scanner startup
1. Scanner sends `HELLO|{seq}|SCANNER` on boot
2. Server clears sequence cache for that scanner
3. Server responds with `HELLO_ACK|{server_seq}|OK`
4. Repeaters clear their cache when forwarding HELLO
5. Scanner blocks all scanning until HELLO_ACK received

**User Experience**:
- If HELLO fails: Scanner shows "Server Handshake Failed!" (red status)
- All buttons disabled except **Reset** (retry) and **Quit**
- User can move closer and click Reset to retry
- GUI fully initialized before handshake (allows error display)

**Files Modified**:
- `lora/node_types.py` - Added HELLO (0x05) and HELLO_ACK (0x06) packet types
- `lora/packet_handler.py` - Added `create_hello_packet()`, `send_hello_handshake()`, `create_hello_ack_packet()`
- `scanner_queue.py` - Added handshake at startup, retry dialog, button state management
- `CaptureLora.py` - Added `handle_hello_packet()` in main receive loop
- `repeater.py` - Added cache clearing when forwarding HELLO packets

### ✅ Collision Avoidance

**Status**: Implemented with randomized delays only (RSSI removed)

**Methods**:
- **Randomized transmission delays** (10-100ms) - Primary method
- **RX guard time** (50ms wait before transmit)
- **Exponential backoff** on retry
- ~~**RSSI-based channel sensing**~~ - **REMOVED** (unreliable)

**Why RSSI was removed**:
- RSSI measures ALL RF signal strength (distance, environment, other sources)
- Cannot distinguish "channel busy" from "moved closer to server"
- Creates false positives
- Proper solution is CAD (Channel Activity Detection) but not available in adafruit_rfm9x

**Documentation**: See `lora/collision_avoidance.py` lines 29-58 for detailed explanation

**Files**:
- `lora/collision_avoidance.py` - Core implementation with documented RSSI decision

### ✅ Repeater with OLED Display

**Status**: Production-ready with battery optimization

**Hardware**: SSD1306 128x64 I2C OLED display
- **No pin conflicts** with RFM9x LoRa (I2C vs SPI)
- **Auto power-off** after 30 seconds (battery saver)
- **50% brightness** (power optimized)
- **<3% total power consumption** (~2-3 mA average)

**Display Features**:
- Startup message (2 seconds)
- Ready status (30s then auto-off)
- Forwarding notifications (brief flash)
- Statistics every 60 seconds (RX/FWD/DROP)
- Error messages (10-15 seconds)
- Graceful shutdown

**Files**:
- `utils/oled_display.py` - Display manager (270 lines)
- `repeater.py` - Integrated OLED calls
- `OLED_SETUP.md` - Complete setup guide with wiring diagrams
- `OLED_IMPLEMENTATION_SUMMARY.md` - Implementation details and testing checklist

### ✅ Setup System

**Status**: Complete automated setup with virtual environment handling

**Components**:
1. **setup.sh** - Bash script with venv automation
   - Checks for/creates virtual environment (.venv or venv)
   - Activates venv automatically
   - Runs Python setup
   - Colored, user-friendly output

2. **setup.py** - Interactive Python setup
   - Prompts for node type (1=Server, 2=Scanner, 3=Repeater)
   - Prompts for node ID (with validation)
   - Creates log/ and data/ directories
   - Copies .iqr files to data/
   - Installs appropriate config to utils/config.py
   - Creates .env with node-specific variables
   - **Installs minimal node-specific dependencies**

3. **Node-Specific Configs** (`configs/`)
   - `config.server.py` - Server settings
   - `config.scanner.py` - Scanner settings
   - `config.repeater.py` - Repeater settings
   - `requirements.server.txt` - Server dependencies (~8 packages, ~150 MB)
   - `requirements.scanner.txt` - Scanner dependencies (~7 packages, ~120 MB)
   - `requirements.repeater.txt` - **Minimal** repeater dependencies (~3-5 packages, ~60-80 MB)

**Usage**:
```bash
./setup.sh  # One command setup
```

**Documentation**:
- `SETUP_README.md` - Complete setup guide
- `REQUIREMENTS_INFO.md` - Dependency philosophy and details
- `QUICKSTART.md` - One-page quick reference

---

## Current System Architecture

### The Server (Node ID: 1)

**Hardware**: Raspberry Pi 4B
**Applications**:
- `CaptureLora.py` - LoRa receiver and data processor
- `mqtt_grid_web.py` - Web interface for teachers

**Responsibilities**:
- Receive packets from scanners (direct or via repeaters)
- Validate and process QR scan requests
- Look up student data (local encrypted files or API)
- Send hierarchyID responses (multi-packet if needed)
- Handle HELLO handshake requests
- Publish data to MQTT for web interface
- Apply business rules (break, release, undo, cleanup)

**Key Features**:
- Async API lookups (with local fallback)
- Teacher optimization (sends hierarchyID not names)
- Multi-packet response handling
- HELLO handshake responder
- Sequence cache management per scanner
- Collision avoidance on transmit

### The Scanner (Node ID: 100-199)

**Hardware**: Raspberry Pi Zero W with QR scanner
**Application**: `scanner_queue.py`

**Responsibilities**:
- **Startup**: Perform HELLO handshake (blocks until success)
- Read QR codes via serial (GPIO 21 trigger)
- Send scan requests to server via LoRa
- Receive student info from server
- Display results in Tkinter GUI (spreadsheet)
- Manage queue operations (break, release, undo, cleanup)
- Decrypt and cache teacher names locally

**Key Features**:
- HELLO handshake with retry on failure
- Teacher name lookup (hierarchyID → name)
- Multi-packet response assembly
- Serial thread for QR scanner
- GUI with real-time updates
- Button state management (disabled during errors)
- Collision avoidance on transmit

**User Interface**:
- Top bar: Status messages (name, connection status)
- Middle: Spreadsheet showing scanned students (Name | Grade | Teacher)
- Bottom: Buttons (Break | Release | Undo | Reset | Quit)
- Error states: Red status, disabled buttons, retry option

### The Repeater (Node ID: 200-256)

**Hardware**: Raspberry Pi Zero W with optional OLED display
**Application**: `repeater.py`

**Responsibilities**:
- Receive packets from any node
- Validate CRC and check duplicate detection
- Check TTL (drop if expired)
- Update sender field to own node ID
- Decrement TTL
- Forward packet with collision avoidance
- Clear sequence cache when forwarding HELLO

**Key Features**:
- **Minimal dependencies** (~60 MB vs ~150 MB)
- Battery/solar optimized
- OLED display with auto-off (30s)
- Statistics tracking (RX/FWD/DROP)
- Thread-safe implementation
- Headless operation (no HDMI needed)

**OLED Display**:
- Shows forwarding activity
- Updates stats every 60 seconds
- Auto power-off after 30s inactivity
- 50% brightness (battery optimized)

---

## Key Implementation Details

### Packet Flow Example

**Scanner QR Scan → Server Response (via Repeater)**:

```
1. Scanner (102) scans QR code "123456789"
2. Scanner creates DATA packet:
   - Source: 102, Dest: 1, Sender: 102
   - Seq: 15, TTL: 3, Flags: ACK_REQ
   - Payload: "102|123456789|1"
3. Scanner transmits (with collision avoidance)

4. Repeater (200) receives packet
   - Validates CRC ✓
   - Checks duplicate: (102, 15) not seen ✓
   - Checks TTL: 3 > 0 ✓
   - Adds (102, 15) to seen_packets
   - Creates repeat packet:
     - Source: 102, Dest: 1, Sender: 200 (updated)
     - Seq: 15, TTL: 2 (decremented), Flags: ACK_REQ | IS_REPEAT
     - Payload: "102|123456789|1"
   - Displays "Forwarding 102 → 1" on OLED
   - Transmits (with collision avoidance)

5. Server (1) receives packet
   - Validates CRC ✓
   - Checks duplicate: (102, 15) not seen ✓
   - Parses payload: beacon=102, code=123456789, distance=1
   - Looks up student (API/local)
   - Finds: name="John Doe", grade="1st", hierarchyID="05"
   - Creates DATA response:
     - Source: 1, Dest: 102, Sender: 1
     - Seq: 87, TTL: 3, Flags: 0
     - Payload: "John Doe|1st|05"
   - Transmits (with collision avoidance)

6. Repeater (200) receives response
   - Validates, checks duplicates, forwards to 102
   - Updates: Sender=200, TTL=2

7. Scanner (102) receives response
   - Validates CRC ✓
   - Parses: name="John Doe", grade="1st", hierarchyID="05"
   - Looks up teacher: "05" → "Mrs. Smith"
   - Displays in spreadsheet: "John Doe | 1st | Mrs. Smith"
```

### HELLO Handshake Flow

**Scanner Startup**:

```
1. Scanner boots, initializes LoRa
2. Creates HELLO packet:
   - Type: HELLO, Dest: 1 (server)
   - Payload: "HELLO|0|SCANNER" (starting seq=0)
3. Sends HELLO (3 attempts, 3s timeout each)

4. Repeater (if between scanner and server):
   - Receives HELLO
   - Clears cache: removes all entries for source=102
   - Forwards HELLO to server

5. Server receives HELLO:
   - Parses: "HELLO|0|SCANNER" from node 102
   - Clears cache: removes all entries for source=102
   - Logs: "HELLO from SCANNER node 102, seq=0"
   - Creates HELLO_ACK:
     - Type: HELLO_ACK, Dest: 102
     - Payload: "HELLO_ACK|87|OK" (server's current seq)
   - Sends HELLO_ACK

6. Scanner receives HELLO_ACK:
   - Parses: "HELLO_ACK|87|OK"
   - Success! Enables all buttons
   - Starts serial thread
   - Ready to scan

If HELLO fails:
- Shows "Server Handshake Failed!" (red)
- Disables Break/Release/Undo buttons
- Keeps Reset (retry) and Quit enabled
- User can move closer and click Reset
```

### Duplicate Detection

**Each node maintains**:
```python
seen_packets = {
    (102, 15),  # Scanner 102, seq 15
    (102, 16),  # Scanner 102, seq 16
    (1, 87),    # Server, seq 87
    ...
}
```

**On packet receive**:
1. Check if `(source_node, sequence_num)` in `seen_packets`
2. If yes: Drop as duplicate
3. If no: Process and add to `seen_packets`

**Cache management**:
- Max 1000 entries (prevents unbounded growth)
- Trimmed to 500 when limit reached
- Cleared for specific source on HELLO

### Multi-Packet Responses

**When server has >240 bytes to send**:

```python
# Example: 3 students found for same QR code
students = [
    "Alice Smith|2nd|05",
    "Bob Smith|4th|07",
    "Carol Smith|Kind|03"
]

# Server sends 3 packets:
Packet 1: Flags=FIRST, Index=1, Total=3, Payload="Alice Smith|2nd|05"
Packet 2: Flags=MORE,  Index=2, Total=3, Payload="Bob Smith|4th|07"
Packet 3: Flags=LAST,  Index=3, Total=3, Payload="Carol Smith|Kind|03"

# Scanner assembles:
- Receives packet with FIRST flag → starts new sequence
- Collects packets until LAST flag received
- Displays all 3 students in spreadsheet
```

---

## File Structure

```
IQRight_Local/
├── lora/                          # Binary packet protocol (Phase 2 ✅)
│   ├── __init__.py               # Public API
│   ├── packet_handler.py         # Core packet logic (482 lines)
│   ├── node_types.py             # Enums (PacketType, NodeType, Flags)
│   └── collision_avoidance.py    # TX optimization
│
├── utils/                         # Shared utilities
│   ├── config.py                 # Active config (copied from configs/)
│   ├── oled_display.py           # Repeater OLED manager
│   └── api_client.py             # Google Cloud Secret Manager
│
├── configs/                       # Node-specific configurations ✅
│   ├── config.server.py          # Server config
│   ├── config.scanner.py         # Scanner config
│   ├── config.repeater.py        # Repeater config
│   ├── requirements.server.txt   # Server dependencies
│   ├── requirements.scanner.txt  # Scanner dependencies
│   └── requirements.repeater.txt # Repeater dependencies (minimal)
│
├── data/                          # Encrypted local data
│   ├── full_load.iqr             # Student database (encrypted)
│   ├── teachers.iqr              # Teacher mappings (encrypted)
│   └── offline.key               # Decryption key
│
├── log/                           # Application logs
│   ├── IQRight_Server.debug      # Server logs
│   ├── IQRight_Scanner.debug     # Scanner logs
│   └── repeater_*.log            # Repeater logs
│
├── CaptureLora.py                 # Server application (551 lines)
├── scanner_queue.py               # Scanner application (700+ lines)
├── repeater.py                    # Repeater application (243 lines)
├── mqtt_grid_web.py               # Web interface for teachers
├── create_key.py                  # Encryption key generator
│
├── setup.sh                       # Setup script with venv handling ✅
├── setup.py                       # Interactive Python setup ✅
├── .env                           # Node-specific environment vars
├── .venv/                         # Python virtual environment
│
└── Documentation/
    ├── CLAUDE.md                  # This file (project overview)
    ├── SETUP_README.md            # Complete setup guide
    ├── QUICKSTART.md              # One-page quick reference
    ├── REQUIREMENTS_INFO.md       # Dependencies explained
    ├── OLED_SETUP.md              # Repeater OLED guide
    └── OLED_IMPLEMENTATION_SUMMARY.md  # OLED implementation details
```

---

## Build & Run Commands

### Setup (One Time)
```bash
./setup.sh  # Interactive setup with venv handling
```

### Running Applications

**Activate virtual environment first:**
```bash
source .venv/bin/activate  # or: source venv/bin/activate
```

**Server:**
```bash
python CaptureLora.py
```

**Scanner:**
```bash
python scanner_queue.py
```

**Repeater:**
```bash
LORA_NODE_ID=200 python repeater.py
```

**Web Interface:**
```bash
flask run  # or: python mqtt_grid_web.py
```

### Testing

**Run tests:**
```bash
pytest                          # All tests
pytest lora/tests/             # Packet protocol tests only
pytest -v                       # Verbose output
pytest --cov=lora              # With coverage
```

**Test without hardware (Mac/Linux):**
```bash
export LOCAL=TRUE
python scanner_queue.py  # or CaptureLora.py
```

### Utilities

**Create encryption key:**
```bash
python create_key.py
```

**Test queue commands:**
```bash
./load_queue.sh    # Add test messages
./release_queue.sh # Release queue
```

---

## Code Style Guidelines and Key Principles

### Key Principles
- Python 3 with Flask and MQTT
- **Binary packet protocol** for LoRa communication
- **Minimal dependencies** per node type (especially repeater)
- Functional, declarative programming; avoid classes except for Flask views and packet dataclasses
- Use type hints for all function signatures
- Lowercase with underscores for directories and files
- Early returns for error conditions (if-return pattern over nested if-else)
- Descriptive variable names with auxiliary verbs (is_active, has_permission)
- Error handling with try/except at start of functions
- JSON deserialization wrapped in exception handling
- Use defensive coding (None checks, type checks)
- Secrets managed via Google Cloud Secret Manager or locally encrypted files
- Config values from environment variables or config.py
- Log errors with stack traces for debugging (debug vs info level)

### Error Handling and Validation
- Prioritize error handling and edge cases
- Handle errors and edge cases at the beginning of functions
- Use early returns for error conditions to avoid deeply nested if statements
- Place the happy path first in the function for improved readability
- Avoid unnecessary else statements; use the if-return pattern instead
- Use guard clauses to handle preconditions and invalid states early
- Implement proper error logging and user-friendly error messages
- **LoRa-specific**: Always validate CRC before processing packets
- **LoRa-specific**: Check for duplicates before any business logic

### Dependencies

**Server**:
- Flask (web interface)
- Flask-SocketIO (real-time updates)
- paho-mqtt (MQTT communication)
- aiohttp (async API calls)
- pandas (data processing)
- cryptography (file encryption)
- adafruit-circuitpython-rfm9x (LoRa hardware)
- google-cloud-secret-manager (optional)

**Scanner**:
- tkinter (built-in GUI)
- tksheet (spreadsheet widget)
- pandas (teacher mapping)
- cryptography (file encryption)
- pyserial (QR scanner)
- RPi.GPIO (scanner hardware)
- adafruit-circuitpython-rfm9x (LoRa hardware)

**Repeater (Minimal)**:
- python-dotenv (config)
- adafruit-circuitpython-rfm9x (LoRa hardware)
- adafruit-circuitpython-ssd1306 (OLED, optional)
- pillow (OLED graphics, optional)

### Flask-Specific Guidelines
- Use Flask application factories for better modularity and testing
- Organize routes using Flask Blueprints for better code organization
- Implement custom error handlers for different types of exceptions
- Use Flask's before_request, after_request, and teardown_request decorators
- Use Flask-SocketIO for real-time web interface updates
- Use Pandas to handle offline data processing
- All data processing should be done offline, results saved to encrypted files
- All files stored locally should be encrypted at rest

### LoRa-Specific Guidelines
- **Always validate CRC** before processing packets
- **Check duplicates** via (source_node, sequence_num) before any logic
- **Use collision avoidance** on all transmissions (randomized delays)
- **Binary serialization** for efficiency (not JSON/text)
- **Multi-packet** for payloads >240 bytes
- **TTL enforcement** in repeaters (prevent infinite loops)
- **Sequence wrapping** handled automatically (0-65535)
- **HELLO handshake** required on scanner startup
- **Clear caches** when forwarding HELLO packets
- **Log packet details** (source, dest, sender, seq, TTL) for debugging

---

## Testing Strategy

### Unit Tests (38 tests, all passing)
- Packet creation and serialization
- CRC validation
- Sequence number wrapping (0-65535)
- Duplicate detection
- Multi-packet handling
- TTL decrementation
- Node type validation

### Integration Testing
- Scanner → Server direct communication
- Scanner → Repeater → Server communication
- Multi-packet responses
- HELLO handshake (success and failure)
- Collision avoidance effectiveness

### E2E Testing (Pre-Production Checklist)
- [ ] Scanner startup HELLO handshake
- [ ] Scanner QR scan → Server lookup → Response display
- [ ] Multi-student response (>1 student per QR code)
- [ ] Scanner operations (Break, Release, Undo, Cleanup)
- [ ] Repeater forwarding (scanner out of direct range)
- [ ] OLED display on repeater (startup, forwarding, stats)
- [ ] HELLO failure handling (move scanner out of range)
- [ ] HELLO retry (move back in range, click Reset)
- [ ] Scanner reboot sequence sync
- [ ] Web interface real-time updates
- [ ] Encrypted file decryption (full_load.iqr, teachers.iqr)
- [ ] Teacher name lookup (hierarchyID → name)
- [ ] Collision avoidance (multiple scanners transmitting)
- [ ] Battery operation (repeater power consumption)

---

## Known Issues and Design Decisions

### RSSI-Based Channel Sensing Removed
**Decision**: Removed RSSI checking from collision avoidance
**Reason**: RSSI measures total RF signal strength (distance, environment) and cannot distinguish "channel busy" from "moved closer to server"
**Alternative**: Rely on randomized delays + exponential backoff
**Future**: Implement CAD (Channel Activity Detection) if library support added
**Reference**: `lora/collision_avoidance.py` lines 29-58

### Sequence Number Wrap
**Handled**: 16-bit sequence (0-65535) with automatic wrapping
**Detection**: Treat sequences as "old" if more than 32768 away (handles wrap)
**Edge case**: Highly unlikely but possible false positive if 32K+ packets lost

### Multi-Packet Assembly
**Current**: Scanner assembles multi-packet responses in memory
**Limitation**: If packets arrive out of order, assembly fails
**Mitigation**: LoRa is generally ordered, retry on failure
**Future**: Implement packet reordering buffer if needed

### HELLO Handshake Requirement
**Design**: Scanner MUST complete HELLO before scanning
**Benefit**: Prevents duplicate detection issues after reboot
**UX**: Clear error message with retry option if handshake fails
**Network**: Repeaters clear cache when forwarding HELLO (ensures sync)

---

## Production Deployment Notes

### Hardware Requirements
- **Server**: Raspberry Pi 4B (or 3B+)
- **Scanner**: Raspberry Pi Zero W
- **Repeater**: Raspberry Pi Zero W (minimal requirements)
- **All nodes**: RFM9x LoRa module (915MHz for US)
- **Repeater (optional)**: SSD1306 128x64 I2C OLED display

### Network Configuration
- Assign unique node IDs (server=1, scanners=100-199, repeaters=200-256)
- Configure frequency (915.23 MHz default, check local regulations)
- Set TX power appropriately (23 dBm max, consider regulations)
- Enable collision avoidance (LORA_ENABLE_CA=TRUE)

### Setup Procedure (Per Device)
1. Run `./setup.sh`
2. Select node type (1/2/3)
3. Enter node ID
4. Confirm setup (creates dirs, copies configs, installs deps)
5. Copy encrypted data files to `data/` (if server/scanner)
6. Start application (see Run Commands above)

### Monitoring
- Check logs in `log/` directory
- Server: `tail -f log/IQRight_Server.debug`
- Scanner: `tail -f log/IQRight_Scanner.debug`
- Repeater: `tail -f log/repeater_*.log`
- Repeater OLED: Visual feedback on forwarding activity

### Troubleshooting
- **HELLO handshake fails**: Check server is running, verify node IDs unique, move closer
- **Packets not received**: Check frequency match, verify TX power, check CRC errors in logs
- **Duplicate warnings**: Normal if packets replicated by multiple repeaters, should be rare
- **Multi-packet assembly fails**: Check for packet loss (CRC errors), verify sequence numbers
- **Repeater not forwarding**: Check TTL not expired, verify not own packet, check duplicate cache

---

## Future Enhancements (Post-MVP)

### High Priority
- [ ] Implement CAD (Channel Activity Detection) when library support available
- [ ] Add packet reordering buffer for multi-packet assembly
- [ ] Implement adaptive TX power based on RSSI feedback
- [ ] Add mesh topology visualization on web interface

### Medium Priority
- [ ] Battery level monitoring for portable nodes
- [ ] Signal strength indicator on scanner GUI
- [ ] Automatic repeater discovery and mesh optimization
- [ ] Packet statistics dashboard (delivery rate, hop count, latency)

### Low Priority
- [ ] QR code display on OLED (for repeater identification)
- [ ] Remote configuration via LoRa commands
- [ ] Frequency hopping for noise immunity
- [ ] Encryption of LoRa packets (currently plaintext)

---

## Related Documentation

For detailed information on specific topics, see:

- **`SETUP_README.md`** - Complete setup guide with manual instructions
- **`QUICKSTART.md`** - One-page quick reference for common tasks
- **`REQUIREMENTS_INFO.md`** - Python dependencies philosophy and comparison
- **`OLED_SETUP.md`** - Repeater OLED display hardware setup and wiring
- **`OLED_IMPLEMENTATION_SUMMARY.md`** - OLED software implementation and testing
- **`lora/collision_avoidance.py`** - In-depth explanation of CA methods and RSSI decision
- **`lora/packet_handler.py`** - Packet protocol implementation with extensive comments

---

## Integration with Main IQRight Project

All services used in the Local Application are part of the main IQRight project:
- **Location**: `~/Documents/Code/IQRight/api_integration_layer`
- **Authentication**: Use secure HTTPS calls with proper authentication headers
- **File operations**: Use `createToken` service before calling main service
- **APIs**: Student lookup, user authentication, pickup data logging

---

## Contact and Support

**Project**: IQRight LoRa Mesh Network
**Status**: MVP Ready for Production E2E Testing
**Last Updated**: 2025
**Version**: 2.0 (Binary Protocol + Mesh + HELLO Handshake)

For issues during E2E testing:
1. Check relevant logs in `log/` directory
2. Review error messages on scanner GUI or OLED
3. Verify HELLO handshake completed (scanner status bar)
4. Check node ID uniqueness across all devices
5. Verify LoRa frequency and TX power match across all nodes
6. Ensure all nodes running same protocol version (2.0)

**Next Steps**: Complete E2E testing, address any discovered issues, proceed to production deployment.
