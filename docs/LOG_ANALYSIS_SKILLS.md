# IQRight Server Log Analysis - Skills & Knowledge Base

**Created**: 2026-02-10
**Source**: Analysis of CaptureLora.py server logs (Dec 13-17, 2025)
**Purpose**: Reusable knowledge for building log analysis agents/skills

---

## 1. LOG FILE STRUCTURE & LOCATIONS

### Server Logs (CaptureLora.py)
- **Active log**: `logs/IQRight_Daemon.debug`
- **Rotated logs**: `logs/IQRight_Daemon.debug.MMDDYY` (date suffix)
- **Max size**: Configured via `MAX_LOG_SIZE` in config.py
- **Rotation**: Uses `logging.handlers.RotatingFileHandler` with `BACKUP_COUNT` backups
- **Format**: `%(asctime)s - %(levelname)s - %(message)s`
- **Levels**: DEBUG (verbose), INFO (normal ops), WARNING (recoverable issues), ERROR (failures)

### Web App Logs (mqtt_grid_web.py)
- **Location**: `logs/IQRight_FE_WEB.debug`
- **Same rotation strategy**

### Device Status Logs
- **Location**: `log/device_status.log` (note: different directory `log/` vs `logs/`)
- **Format**: `%(asctime)s - %(message)s`
- **Content**: Repeater battery/voltage/temperature status

### Adaptive Logging (Implemented Feb 2026)
The server uses 3 logging states to reduce idle noise:
- **IDLE** (before HELLO handshake): Logs timeouts once every 5 minutes
- **ACTIVE** (after HELLO received): Logs every timeout for close monitoring during operations
- **WIND_DOWN** (15 min no valid packets): Returns to 5-minute interval (operation done for the day)

State transitions are logged:
```
Server started in IDLE mode - logging timeouts every 5 minutes until HELLO received
=== SWITCHING TO ACTIVE MODE - monitoring all packets ===
=== SWITCHING TO IDLE MODE - no valid packets for 15 minutes ===
```

### Key Observation: Log Volume (Pre-Feb 2026 logs)
- **99.7% of server log lines were idle timeouts** (`No packet received (timeout)`)
- A single day could produce 80-90MB of logs, almost entirely noise
- When analyzing OLD logs, ALWAYS filter out timeout lines first or search for specific patterns
- NEW logs with adaptive logging will be significantly smaller

---

## 2. THE DATA PIPELINE (CaptureLora.py)

The server processes QR code scans through a 4-stage pipeline. Each stage has distinct log signatures.

### Stage 1: LoRa Packet Reception

**Success indicators:**
```
LoRaPacket(type=DATA, src=102, dst=1, sender=102, seq=4, ttl=3, ...)
Received data from scanner {node}: Beacon={beacon}, Code={code}, Distance={distance}
```

**Key fields to extract:**
- `src` = Scanner node ID (100-199)
- `seq` = Sequence number (duplicate detection)
- `ttl` = Time-to-live (3=direct, 2=one hop via repeater, 1=two hops)
- Payload format: `{beacon}|{code}|{distance}`

**Failure indicators:**
- No `Received data from scanner` entries = packets not reaching server
- `Invalid DATA packet format` = corrupted payload
- `Invalid UTF-8 String` = binary corruption

**Other packet types (non-data):**
```
HELLO PACKET RECEIVED       -> Scanner handshake (reboot/reconnect)
STATUS from Node             -> Repeater health check
Received command '{cmd}'     -> Scanner command (break/release/undo/cleanup)
```

**Discard indicators (normal behavior):**
```
Discarding: own_packet_looped  -> Server hearing its own packet via repeater (NORMAL)
Discarding: duplicate          -> Same packet received twice (NORMAL if < 5% of traffic)
```

### Stage 2: Data Lookup (API + Local)

**The lookup strategy is parallel**: API and local run concurrently, first result wins.

**API lookup log sequence:**
```
API URL: https://integration.iqright.app/api/apiGetUserInfo
Payload: {'searchCode': '{code}'}
Headers: {Content-Type, accept, caller, idFacility}
Auth username: {username}
Attempting API call...
```

**API success:**
```
Using API results (completed first)
```

**API failure patterns:**
```
Client error during API call: [Errno 104] Connection reset by peer  -> Server unreachable
Client error during API call: Server disconnected                    -> Connection dropped
API call timed out after {N} seconds                                 -> Timeout (configurable)
Unexpected error during API call: {error}                            -> Catchall
API getUserAccess request failed on getting secrets                   -> Credential issue
```

**Local lookup log sequence:**
```
Attempting Student Local Lookup...
Using local results                      -> SUCCESS
Couldn't find Code: {code} locally       -> Code not in local DB
```

**Lookup result:**
```
Using API results      -> API won the race
Using local results    -> Local won (or API failed)
Timeout reached, waiting for remaining tasks...  -> Both slow, waiting
No results from API or local lookup              -> Both failed
```

**Key diagnostic**: If "Couldn't find Code" appears, check the code value for:
- Leading whitespace/null bytes: `\x00\x00\x01\x0031P22510583` (serial buffer corruption)
- Concatenated duplicates: `P1871058731P18710587` (QR scanner double-read)
- The pattern `31` between codes = ASCII "1" from the distance field leaking into the next scan

### Stage 3: LoRa Response to Scanner

**Success:**
```
Sent DATA to scanner {node}: {name}|{grade}|{hierarchyID} [{index}/{total}]
Sent CMD to scanner {node}: {command} [0/0]
```

**Multi-packet format**: `[1/4]` means packet 1 of 4 (multi-student family)

**Collision avoidance logs (before each send):**
```
Random delay: {N}ms                    -> Anti-collision delay (10-100ms)
Guard delay: 50ms (RSSI check disabled) -> RX guard period
Sending with CA (attempt {N}/3)        -> Transmission attempt
Send successful                        -> CA-level success
```

**Failure:**
```
FAILED to send data to Scanner: {json}
Failed to send DATA to scanner {node}: {msg}
Error in sendDataScanner: {error}
```

### Stage 4: MQTT Publishing

**Success sequence:**
```
[MQTT-TX] Sending to MQTT: {json_payload}
[MQTT-TX] SUCCESS: Topic={topic}, MsgID={id}, QoS=1
MQTT Data Message Sent
```

**MQTT topic routing:**
- Student data: `Topic={TOPIC_PREFIX}{hierarchyID}` (e.g., `Class96`)
- Commands: `Topic=IQRSend` (via `COMMAND_TOPIC`)

**Failure:**
```
[MQTT-TX] FAILED: Topic={topic}, Status={status}, Error={errno}
MQTT ERROR publishing data
MQTT ERROR publishing command ACK
```

**MQTT Status codes:**
- Status 0 = Success
- Status 7 = `MQTT_ERR_CONN_LOST` (broker connection dropped)

**Reconnection pattern:**
```
Disconnected from MQTT
Connected to MQTT Server
```
The `publishMQTT` function retries up to 5 times with reconnect between each attempt.

---

## 3. DIAGNOSTIC DECISION TREE

Use this tree to diagnose "QR codes scanned but nothing on web pages":

```
Q1: Are DATA packets being received?
    grep "Received data from scanner" logs/IQRight_Daemon.debug

    NO -> Problem is LoRa reception
        - Check: Is the server application running?
        - Check: LoRa frequency/config match between scanner and server
        - Check: "HELLO_ACK sent successfully" (handshake completed?)
        - Check: HELLO handshake failures

    YES -> Q2: Are lookups succeeding?
        grep "Using local results\|Using API results" logs/IQRight_Daemon.debug

        NO -> Problem is data lookup
            - Check: "Couldn't find Code" (corrupted QR codes?)
            - Check: "No results from API or local" (code not in DB?)
            - Check: API errors (connection resets, timeouts?)
            - Check: Is the local file loaded? ("UNABLE TO OPEN USER FILE")

        YES -> Q3: Are responses sent to scanner?
            grep "Sent DATA to scanner\|FAILED to send" logs/IQRight_Daemon.debug

            NO/FAILURES -> Problem is LoRa transmission
                - Check: "Error in sendDataScanner" (code bug?)
                - Check: CA retry exhaustion
                - Check: LoRa hardware issues

            YES -> Q4: Are MQTT messages published?
                grep "MQTT-TX.*SUCCESS\|MQTT-TX.*FAILED" logs/IQRight_Daemon.debug

                FAILURES -> Problem is MQTT
                    - Check: Status=7 (broker connection lost)
                    - Check: Reconnection pattern
                    - Check: Broker is running (mosquitto)

                SUCCESSES -> Q5: Are topics correct?
                    grep "Topic=" logs/IQRight_Daemon.debug | sort | uniq -c

                    MALFORMED TOPICS -> Bug in topic construction
                        - Pattern: "Class['cmd'..." = command list as string
                        - Pattern: "Classcmd|ack|..." = raw payload as topic
                        - Fix: Ensure command routing uses COMMAND_TOPIC

                    CORRECT TOPICS -> Problem is NOT in CaptureLora.py
                        -> Check mqtt_grid_web.py logs
                        -> Check: MQTT subscription matching topics
                        -> Check: SocketIO connection to browser
                        -> Check: Browser console for JS errors
```

---

## 4. KEY SEARCH PATTERNS (grep commands)

### Quick Health Check
```bash
# Pipeline overview (run all 4 in sequence)
echo "=== PACKETS RECEIVED ===" && grep -c "Received data from scanner" logs/IQRight_Daemon.debug
echo "=== LOOKUPS SUCCEEDED ===" && grep -c "Using local results\|Using API results" logs/IQRight_Daemon.debug
echo "=== SENT TO SCANNER ===" && grep -c "Sent DATA to scanner" logs/IQRight_Daemon.debug
echo "=== MQTT PUBLISHED ===" && grep -c "MQTT-TX.*SUCCESS" logs/IQRight_Daemon.debug
echo "=== MQTT FAILED ===" && grep -c "MQTT-TX.*FAILED" logs/IQRight_Daemon.debug
echo "=== ERRORS ===" && grep -c "ERROR" logs/IQRight_Daemon.debug
```

### Date/Time Range
```bash
# First and last log entry
head -1 logs/IQRight_Daemon.debug
tail -1 logs/IQRight_Daemon.debug
```

### Error Summary
```bash
# Unique error messages (deduplicated)
grep "ERROR" logs/IQRight_Daemon.debug | sed 's/.*ERROR - //' | sort | uniq -c | sort -rn | head -20
```

### MQTT Topic Distribution
```bash
# What topics are being published to (and how many)
grep "Topic=" logs/IQRight_Daemon.debug | sed 's/.*Topic=\([^,]*\).*/\1/' | sort | uniq -c | sort -rn
```

### Transaction Tracing
```bash
# Find a specific QR code's journey through the pipeline
CODE="P22510583"
grep "$CODE" logs/IQRight_Daemon.debug
```

### Lookup Failure Analysis
```bash
# What codes failed lookup (usually corrupted QR data)
grep "Couldn't find Code\|No data found for code" logs/IQRight_Daemon.debug | tail -20
```

### Scanner Activity
```bash
# Which scanners are active
grep "Received data from scanner" logs/IQRight_Daemon.debug | sed 's/.*scanner \([0-9]*\).*/\1/' | sort | uniq -c
```

### HELLO Handshake Status
```bash
# Handshake success/failure
grep "HELLO_ACK sent successfully\|Failed to send HELLO_ACK" logs/IQRight_Daemon.debug | tail -10
```

### Connection Stability
```bash
# MQTT reconnections
grep "Connected to MQTT\|Disconnected from MQTT" logs/IQRight_Daemon.debug | tail -20
```

---

## 5. KNOWN BUGS & PATTERNS

### BUG-001: Malformed MQTT Command Topics (FIXED in current code)
- **Symptom**: `Topic=Class['cmd', 'ack', 'break']` or `Topic=Classcmd|ack|cleanup}`
- **Impact**: Command messages (break/release/cleanup) published to garbage topics; web UI never receives them
- **Root Cause**: Old code passed the `command` variable (a Python list) as `topicSufix` instead of the string `"command"`
- **Fix**: Current code uses `publishMQTT(sendObj, topicSufix="command")` which routes to `COMMAND_TOPIC="IQRSend"`
- **Detection**: `grep "Class\[" logs/IQRight_Daemon.debug | wc -l` (should be 0 after fix)

### BUG-002: LoRaTransceiver Missing create_packet Method (APPEARS FIXED)
- **Symptom**: `Error in sendDataScanner: 'LoRaTransceiver' object has no attribute 'create_packet'`
- **Impact**: Server looked up student data successfully but failed to send LoRa response
- **Root Cause**: Method name mismatch -- code called `create_packet()` but the class has `create_data_packet()`
- **Fix**: Current code uses `transceiver.create_data_packet()` and `transceiver.create_cmd_packet()`
- **Detection**: `grep "create_packet" logs/IQRight_Daemon.debug | wc -l` (should be 0 after fix)

### PATTERN-001: QR Scanner Serial Buffer Corruption
- **Symptom**: Corrupted codes with null bytes (`\x00\x00\x01\x00`), leading `31`, or concatenated duplicates
- **Frequency**: ~10% of scans during affected sessions
- **Pattern A**: `\x00\x00\x01\x0031P22510583` (null prefix + "31" + valid code)
- **Pattern B**: `P1871058731P18710587` (valid code + "31" + valid code repeated)
- **The "31" character**: ASCII "1", likely the distance field from payload format `{beacon}|{code}|1` leaking across scan boundaries
- **Root Cause**: QR scanner serial buffer not being fully flushed between reads
- **Workaround**: Add input sanitization to extract valid code pattern `P\d{7,8}` from corrupted data
- **Detection**: `grep "Couldn't find Code" logs/IQRight_Daemon.debug | grep -E "31P|\\\\x00|P[0-9]+P[0-9]"`

### PATTERN-002: API Always Failing (Offline Mode)
- **Symptom**: 0% API success rate, all lookups fall back to local
- **Errors**: `Connection reset by peer`, `Server disconnected`
- **Impact**: Every transaction wastes time waiting for API timeout before using local results
- **Root Cause**: API at `integration.iqright.app` unreachable from server's network
- **Secondary impact**: Generates noisy `WARNING:Timeout reached, waiting for remaining tasks...` on every transaction
- **Detection**: `grep -c "Using API results" logs/IQRight_Daemon.debug` (if 0, API is not working)

### PATTERN-003: own_packet_looped (Normal, High Volume)
- **Symptom**: `Discarding: own_packet_looped` in logs
- **Explanation**: Server transmits a response, repeater forwards it, server hears its own packet back
- **Impact**: None (correctly discarded), but adds log noise
- **Verification**: Looped packets always have TTL = original TTL - 1 (confirming one repeater hop)
- **Detection**: `grep -c "own_packet_looped" logs/IQRight_Daemon.debug` (normal if proportional to sends)

### PATTERN-004: Excessive HELLO Traffic
- **Symptom**: More HELLO handshakes than DATA packets
- **In observed logs**: 97 HELLOs vs 62 DATA packets
- **Indicates**: Scanner being restarted frequently (testing, crashes, or unnecessary reboots)
- **Acceptable ratio**: < 1 HELLO per 10 DATA packets in production
- **Detection**: Compare `grep -c "HELLO PACKET RECEIVED"` vs `grep -c "Received data from scanner"`

---

## 6. PERFORMANCE METRICS & BASELINES

### Observed Baselines (Dec 2025 UAT)

| Metric | Value | Notes |
|--------|-------|-------|
| End-to-end latency (single student) | ~2.0s | Receive to MQTT publish |
| End-to-end latency (4 students) | ~3.3s | Multi-packet response |
| Local lookup time | <10ms | Very fast |
| API lookup time | N/A (always fails) | Target: <2s |
| Collision avoidance delay | 30-100ms random + 50ms guard | Per transmission |
| LoRa send success rate | 98.2% | 112/114 packets |
| MQTT publish success rate | 95.2% | 178/187 attempts |
| MQTT retry success | 100% | All retries succeeded |
| Local lookup success rate | 78.5% | 84/107 (failures = corrupted QR codes) |
| Duplicate detection rate | ~16% | 25 duplicates out of ~160 total received |
| Own-packet-loop rate | Varies | Higher with more repeaters |

### Thresholds for Alerting

| Metric | Warning | Critical |
|--------|---------|----------|
| LoRa send failure rate | > 5% | > 15% |
| MQTT publish failure rate | > 5% | > 20% |
| Lookup failure rate | > 10% | > 30% |
| HELLO/DATA ratio | > 1:5 | > 1:1 |
| Consecutive MQTT Status=7 | > 3 | > 10 |
| API success rate | < 50% | 0% |

---

## 7. LOG ANALYSIS WORKFLOW

### Step 1: Assess Log File Health
```bash
# Size, line count, date range for all log files
du -h logs/IQRight_Daemon.debug*
wc -l logs/IQRight_Daemon.debug*
head -1 logs/IQRight_Daemon.debug && tail -1 logs/IQRight_Daemon.debug
```

### Step 2: Pipeline Health Check
```bash
# Quick 4-stage pipeline check
for pattern in "Received data from scanner" "Using local results\|Using API results" "Sent DATA to scanner" "MQTT-TX.*SUCCESS"; do
  echo "=== $pattern ===" && grep -c "$pattern" logs/IQRight_Daemon.debug
done
```

### Step 3: Error Categorization
```bash
# Group errors by type
grep "ERROR" logs/IQRight_Daemon.debug | sed 's/[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9:,]*//' | sort | uniq -c | sort -rn | head -20
```

### Step 4: Trace Specific Transactions
```bash
# Find a specific scan and trace its full lifecycle
LINE=$(grep -n "Received data from scanner.*Code=P22510583" logs/IQRight_Daemon.debug | tail -1 | cut -d: -f1)
sed -n "$((LINE)),$((LINE+30))p" logs/IQRight_Daemon.debug
```

### Step 5: Cross-Reference with Web Logs
```bash
# Check if MQTT messages arrived at the web app
grep "MQTT-RX" logs/IQRight_FE_WEB.debug | tail -20
grep "SOCKETIO-TX" logs/IQRight_FE_WEB.debug | tail -20
```

---

## 8. ANALYSIS RESULTS: DEC 2025 UAT INVESTIGATION

### Problem Statement
"Reading a lot of QR codes but not getting anything on web pages"

### Pipeline Trace Results

| Stage | Status | Count | Details |
|-------|--------|-------|---------|
| 1. LoRa Reception | WORKING | 62 DATA packets | All from scanner 102, distance=1 |
| 2. Data Lookup | WORKING (local only) | 84 succeeded / 23 failed | API 0% success (unreachable), local 78.5% |
| 3. LoRa Response | WORKING | 112/114 sent | 2 failures (create_packet bug, now fixed) |
| 4. MQTT Publish | WORKING (after fix) | 121 student data + 21 commands correct | 45 commands to malformed topics (bug fixed mid-session) |

### Root Cause Assessment

**The CaptureLora.py server IS working correctly in its current code version.**

Student data IS being published to the correct MQTT topics (`Class96`, `Class89`, `Class85`, etc.). The 121 successful student data publishes confirm end-to-end functionality from LoRa reception through MQTT publishing.

**The problem of "nothing on web pages" is NOT in CaptureLora.py.** The investigation must continue to:

1. **mqtt_grid_web.py** - Check if it's subscribing to the right MQTT topics and if SocketIO is emitting correctly
2. **Browser client** - Check if SocketIO connection is established and receiving events
3. **MQTT broker** - Verify messages are being delivered from CaptureLora.py publisher to mqtt_grid_web.py subscriber

### Bugs Found & Fixed During Testing

1. **Malformed MQTT command topics** (FIXED): Commands went to `Class['cmd', 'ack', 'break']` instead of `IQRSend`. This prevented break/release/cleanup from reaching the web UI, which could break the Virtual_List state management.

2. **Missing create_packet method** (FIXED): 2 transactions failed to send LoRa responses due to method name mismatch.

### Issues Still Open

1. **QR scanner buffer corruption**: ~10% of scans produce garbled codes. Needs input sanitization.
2. **API unreachable**: All API calls fail. Local fallback works but wastes timeout waiting.
3. **Log volume**: 99.7% of log lines are idle timeouts. Need log level filtering.
4. **Web UI investigation needed**: Must analyze `logs/IQRight_FE_WEB.debug` to complete diagnosis.

### Recommended Next Steps

1. Analyze `logs/IQRight_FE_WEB.debug` for MQTT-RX and SOCKETIO-TX patterns
2. Verify the MQTT broker is routing messages correctly between publishers and subscribers
3. Check browser console for SocketIO connection issues
4. Add QR code input sanitization to handle corrupted scans
5. Reduce log verbosity for idle timeouts (log every Nth timeout, or use TRACE level)

---

## 9. AGENT SKILL DEFINITIONS

### Skill: server-log-health-check
**Trigger**: "Check server health" / "Is the server working?"
**Actions**:
1. Read last 100 lines of active log
2. Run pipeline health check (4 grep counts)
3. Check for recent errors (last 20 ERROR lines)
4. Report pipeline status and any issues

### Skill: trace-qr-scan
**Trigger**: "Trace scan for code {X}" / "What happened to code {X}?"
**Actions**:
1. Search all logs for the code
2. Extract the full transaction context (30 lines after match)
3. Report: received? -> looked up? -> found? -> sent? -> published? -> topic?

### Skill: mqtt-diagnosis
**Trigger**: "Check MQTT" / "Why aren't messages reaching the web?"
**Actions**:
1. Count MQTT-TX SUCCESS vs FAILED
2. Check topic distribution for malformed topics
3. Check connection stability (connect/disconnect patterns)
4. Cross-reference with web app logs if available

### Skill: error-report
**Trigger**: "Show errors" / "What's failing?"
**Actions**:
1. Count and categorize all ERROR messages
2. Group by error type with frequency
3. Show most recent examples
4. Provide recommendations per error type

### Skill: scanner-status
**Trigger**: "Scanner status" / "Is scanner {N} connected?"
**Actions**:
1. Find last DATA packet from specified scanner
2. Check HELLO handshake history
3. Report: last active time, handshake status, error rate

### Skill: log-cleanup-report
**Trigger**: "Log cleanup" / "Why are logs so big?"
**Actions**:
1. Check log file sizes
2. Count idle timeout lines vs meaningful lines
3. Calculate signal-to-noise ratio
4. Recommend log configuration changes