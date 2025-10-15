# LoRa Ping Test Guide

Complete guide for using the ping-pong test scripts to determine optimal repeater placement.

## Overview

The ping test helps you determine:
- **Signal strength** between scanner and server (RSSI values)
- **When a repeater is needed** (scanner out of server range)
- **Optimal repeater placement** (maximize RSSI from both scanner and server)
- **Network performance** (packet success rate, response times)

## Test Scripts

| Script | Node Type | Purpose |
|--------|-----------|---------|
| `test_ping_server.py` | Server (Node 1) | Receives PINGs, sends PONGs, logs RSSI |
| `test_ping_scanner.py` | Scanner (100-199) | Sends PINGs, displays signal strength |
| `test_ping_repeater.py` | Repeater (200-256) | Forwards packets, shows RSSI on OLED |

## Quick Start

### 1. Test Direct Connection (Scanner → Server)

**On Server:**
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate  # or: source venv/bin/activate
python3 test_ping_server.py
```

**On Scanner:**
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate
python3 test_ping_scanner.py
```

**Scanner GUI will show:**
- Current RSSI (signal strength)
- Signal quality (EXCELLENT/GOOD/FAIR/POOR)
- Success rate (% of PONGs received)
- Whether responses are direct or via repeater

**What to look for:**
- **RSSI ≥ -70 dBm**: Excellent, no repeater needed
- **RSSI -70 to -85 dBm**: Good, repeater optional
- **RSSI -85 to -100 dBm**: Fair, repeater recommended
- **RSSI < -100 dBm**: Poor, repeater required
- **Success rate < 80%**: Repeater required

### 2. Position the Repeater

If signal is FAIR or POOR, you need a repeater.

**On Repeater:**
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate
LORA_NODE_ID=200 python3 test_ping_repeater.py
```

**Repeater OLED will show:**
```
┌────────────────────────────┐
│ PING TEST                  │
│────────────────────────────│
│ Last: PING 102->1          │  ← Last packet forwarded
│ RSSI: -65 dBm (GOOD)       │  ← Signal strength
│ ──────────────────────────│
│ PING>: 15  PONG<: 14       │  ← Counters
│ Tot: 29  Drop: 0           │
│ Avg: -68 dBm               │  ← Average RSSI
└────────────────────────────┘
```

**Positioning Strategy:**
1. Start with repeater near server
2. Slowly move repeater toward scanner location
3. Watch OLED RSSI values (should show both PING and PONG)
4. Watch scanner GUI (should show "Via Repeater" responses)
5. Find spot where both have GOOD signal (-70 to -85 dBm)

**Optimal Placement:**
- Scanner → Repeater RSSI: ≥ -85 dBm
- Repeater → Server RSSI: ≥ -85 dBm
- Repeater displays both PING (scanner→server) and PONG (server→scanner)
- Scanner GUI shows responses "via Repeater 200"

### 3. Verify Final Placement

Once repeater is positioned:

**Check Scanner GUI:**
- "Via Repeater" count should be increasing
- RSSI should improve (closer to -70 dBm)
- Success rate should be ≥ 90%

**Check Repeater OLED:**
- Both PING and PONG counts increasing
- Average RSSI should be GOOD or better
- Drop count should be low (< 5%)

**Check Server Console:**
- Should see packets from scanner with "via Repeater 200"
- RSSI values should be GOOD

## Understanding RSSI Values

### Signal Strength Chart

| RSSI Range | Quality | Meaning | Action |
|------------|---------|---------|--------|
| ≥ -50 dBm | EXCELLENT | Very close range | No action needed |
| -50 to -70 dBm | EXCELLENT | Optimal signal | No repeater needed |
| -70 to -85 dBm | GOOD | Reliable connection | Repeater optional |
| -85 to -100 dBm | FAIR | Marginal signal | Repeater recommended |
| -100 to -110 dBm | POOR | Unreliable | Repeater required |
| < -110 dBm | VERY POOR | No connection | Move closer or add repeater |

### Factors Affecting RSSI

**Environmental:**
- **Walls/buildings**: -5 to -30 dBm loss
- **Trees/foliage**: -10 to -20 dBm loss
- **Metal structures**: -20 to -40 dBm loss
- **Distance**: ~6 dBm loss per doubling of distance

**Hardware:**
- **Antenna orientation**: Can vary by 10-20 dBm
- **Antenna quality**: Better antenna = stronger signal
- **TX power**: Higher power = stronger signal (but check regulations)

**Interference:**
- **Other RF sources**: WiFi, Bluetooth, microwaves
- **Weather**: Rain/fog can attenuate signal

## Detailed Usage

### Server Script

**Command:**
```bash
python3 test_ping_server.py
```

**Output:**
```
============================================================
LoRa PING-PONG TEST - SERVER
============================================================
Node ID:    1
Frequency:  915.23 MHz
TX Power:   23 dBm
============================================================

Listening for PING packets...
Press Ctrl+C to stop and show statistics

PING #1 from Node 102 (direct)
  RSSI: -68 dBm | TTL: 3 | Timestamp: 1708123456
  → PONG sent to Node 102

PING #2 from Node 102 (via Repeater 200)
  RSSI: -72 dBm | TTL: 2 | Timestamp: 1708123458
  → PONG sent to Node 102
```

**Press Ctrl+C to see statistics:**
```
============================================================
PING-PONG SERVER STATISTICS
============================================================

Node 102 (Scanner):
  PINGs received: 25
  PONGs sent:     25
  Last RSSI:      -68 dBm
  Avg RSSI:       -71.2 dBm (GOOD)

Node 200 (Repeater):
  PINGs received: 0
  PONGs sent:     0
  Last RSSI:      -65 dBm
  Avg RSSI:       -67.5 dBm (EXCELLENT)
============================================================
```

### Scanner Script

**Command:**
```bash
python3 test_ping_scanner.py
```

**GUI Features:**
- **Status bar**: Shows initialization and test status
- **Signal strength**: Large RSSI display with quality indicator
- **Statistics**:
  - PINGs sent
  - PONGs received
  - Direct responses (server without repeater)
  - Via repeater responses
  - Average RSSI
  - Success rate
- **Activity log**: Real-time packet events
- **Buttons**:
  - **Start Ping Test**: Begin sending PINGs
  - **Stop Test**: Pause testing
  - **Quit**: Exit application

**Interpreting Results:**

**Good Direct Connection:**
```
Signal Strength (RSSI): -68 dBm (GOOD)

Statistics:
  PINGs Sent:       20
  PONGs Received:   19
  Direct Responses: 19
  Via Repeater:     0
  Average RSSI:     -69.5 dBm
  Success Rate:     95.0%
```
→ No repeater needed

**Poor Direct Connection:**
```
Signal Strength (RSSI): -98 dBm (FAIR)

Statistics:
  PINGs Sent:       20
  PONGs Received:   12
  Direct Responses: 12
  Via Repeater:     0
  Average RSSI:     -96.3 dBm
  Success Rate:     60.0%
```
→ Repeater required

**With Repeater:**
```
Signal Strength (RSSI): -72 dBm (GOOD)

Statistics:
  PINGs Sent:       20
  PONGs Received:   19
  Direct Responses: 2
  Via Repeater:     17
  Average RSSI:     -74.1 dBm
  Success Rate:     95.0%
```
→ Repeater working well

### Repeater Script

**Command:**
```bash
LORA_NODE_ID=200 python3 test_ping_repeater.py
```

**Console Output:**
```
============================================================
LoRa PING-PONG TEST - REPEATER 200
============================================================
Frequency:  915.23 MHz
TX Power:   23 dBm
Collision Avoidance: ENABLED
============================================================

Initializing OLED display...
OLED display initialized

Initializing LoRa transceiver...
Repeater ready, listening for PING/PONG packets...
Press Ctrl+C to stop

PING forwarding: 102 → 1 (RSSI: -68 dBm, TTL: 3)
PONG forwarding: 1 → 102 (RSSI: -71 dBm, TTL: 3)
PING forwarding: 102 → 1 (RSSI: -67 dBm, TTL: 3)
PONG forwarding: 1 → 102 (RSSI: -72 dBm, TTL: 3)
```

**OLED Display Elements:**

```
┌────────────────────────────┐
│ PING TEST                  │  ← Header
│────────────────────────────│
│ Last: PING 102->1          │  ← Last packet info
│ RSSI: -65 dBm (GOOD)       │  ← Signal strength + quality
│ ──────────────────────────│
│ PING>: 15  PONG<: 14       │  ← PING/PONG counts
│ Tot: 29  Drop: 0           │  ← Total forwarded, dropped
│ Avg: -68 dBm               │  ← Average RSSI
└────────────────────────────┘
```

**What to Watch:**
- **PING> count**: Should increase (scanner → server packets)
- **PONG< count**: Should increase (server → scanner packets)
- **RSSI values**: Should be GOOD or better (-85 dBm or higher)
- **Drop count**: Should be low (< 5 out of 100)

## Troubleshooting

### No PONGs Received on Scanner

**Symptoms**: Scanner sends PINGs but receives no PONGs

**Possible Causes:**
1. Server not running
2. Server script not started
3. Signal too weak (RSSI < -110 dBm)
4. Frequency mismatch between nodes
5. Node IDs not configured correctly

**Solutions:**
```bash
# On server, verify running:
ps aux | grep test_ping_server

# Check logs for errors:
tail -f log/IQRight_Server.debug

# Verify frequency in .env:
grep LORA_FREQUENCY .env

# Verify node IDs:
echo $LORA_NODE_ID  # Should be 1 on server
```

### Repeater Not Forwarding

**Symptoms**: Repeater OLED shows "Tot: 0", no packets forwarded

**Possible Causes:**
1. Repeater out of range of both scanner and server
2. Duplicate detection (repeater already saw packets)
3. TTL expired (packets died before reaching repeater)

**Solutions:**
```bash
# Move repeater closer to scanner or server

# Check repeater logs:
grep -i "forward" log/repeater_*.log

# Verify repeater node ID (200-256):
echo $LORA_NODE_ID
```

### Poor RSSI Despite Close Range

**Symptoms**: Nodes are close but RSSI is -90 dBm or worse

**Possible Causes:**
1. Antenna not connected properly
2. Antenna orientation (polarization mismatch)
3. Metal/concrete between nodes
4. Interference from other RF sources

**Solutions:**
- Check antenna connections (tighten SMA connectors)
- Try different antenna orientations (vertical vs horizontal)
- Move away from metal structures
- Check for interference:
  ```bash
  # On Raspberry Pi, scan for WiFi:
  sudo iwlist wlan0 scan | grep -i frequency

  # Disable WiFi temporarily to test:
  sudo ifconfig wlan0 down
  ```

### Repeater Shows Only PING or Only PONG

**Symptoms**: Repeater forwards PINGs but not PONGs (or vice versa)

**Possible Causes:**
1. Repeater closer to one node than the other
2. Directional antenna pointing wrong way
3. One direction has more obstacles

**Solutions:**
- Move repeater to midpoint between scanner and server
- Check RSSI values on OLED (should be similar for both)
- Try line-of-sight placement if possible

### High Drop Rate

**Symptoms**: Repeater shows many dropped packets

**Possible Causes:**
1. Duplicate detection working correctly (not an error)
2. Multiple repeaters forwarding same packet
3. Packet corruption (CRC failures)

**Expected Behavior:**
- Some drops are normal (duplicate detection)
- Drop rate < 10% is acceptable
- Drop rate > 25% indicates a problem

**Solutions:**
- Check CRC errors in logs
- Reduce TX power if too high (causing distortion)
- Check antenna connections

## Best Practices

### Initial Site Survey

1. **Start at server location**
   - Run server script
   - Walk to scanner location with scanner running test
   - Note RSSI values every 10 meters
   - Mark where RSSI drops below -85 dBm

2. **Find repeater spot**
   - Start at midpoint between server and scanner
   - Run repeater test script
   - Adjust position for best RSSI from both directions
   - Aim for RSSI ≥ -85 dBm in both directions

3. **Test complete path**
   - Run all three scripts simultaneously
   - Verify packets flow: Scanner → Repeater → Server → Repeater → Scanner
   - Check success rate ≥ 90%
   - Monitor for 5-10 minutes to ensure stability

### Repeater Placement Tips

**Good Locations:**
- Line of sight to both scanner and server
- Elevated position (higher = better)
- Away from metal structures
- Protected from weather
- Access to power (solar panel or battery)

**Avoid:**
- Basements or underground
- Inside metal buildings
- Near high-power RF sources (cell towers, radar)
- Locations with no power access

### Multiple Repeaters

If you need multiple repeaters (very long distances):

1. **Test each segment individually**
   - Scanner → Repeater 1
   - Repeater 1 → Repeater 2
   - Repeater 2 → Server

2. **Check TTL values**
   - Packets start with TTL=3
   - Each hop decrements TTL
   - Packet dropped when TTL=0
   - Max hops = 3 (scanner → R1 → R2 → server)

3. **Monitor for loops**
   - Repeaters should not forward to each other in a loop
   - Check logs for "own packet loop" warnings

## Performance Metrics

### Target Values

| Metric | Good | Acceptable | Poor |
|--------|------|------------|------|
| RSSI | ≥ -70 dBm | -70 to -95 dBm | < -95 dBm |
| Success Rate | ≥ 95% | 80-95% | < 80% |
| Round-Trip Time | < 500ms | 500-1000ms | > 1000ms |
| Drop Rate | < 5% | 5-15% | > 15% |

### Real-World Examples

**School Parking Lot (Direct Connection):**
- Distance: 50 meters
- RSSI: -65 dBm (EXCELLENT)
- Success Rate: 98%
- **Result**: No repeater needed

**School with Building Between:**
- Distance: 80 meters with building
- RSSI (direct): -105 dBm (POOR)
- Success Rate: 45%
- **Solution**: Added repeater on building roof
- RSSI (via repeater): -72 dBm (GOOD)
- Success Rate: 97%

**Large Campus:**
- Distance: 200 meters
- RSSI (direct): No connection
- **Solution**: Two repeaters at 70m and 140m
- RSSI (via repeaters): -78 dBm (GOOD)
- Success Rate: 93%

## Stopping the Tests

**Scanner GUI:**
- Click "Stop Test" button
- Click "Quit" to exit

**Server Console:**
- Press Ctrl+C
- View final statistics

**Repeater:**
- Press Ctrl+C
- OLED shows "Test Complete" screen
- Final stats displayed in console

## Next Steps

After positioning repeater:

1. **Stop test scripts**
2. **Start production applications**:
   ```bash
   # Server
   python3 CaptureLora.py

   # Scanner
   python3 scanner_queue.py

   # Repeater
   LORA_NODE_ID=200 python3 repeater.py
   ```

3. **Test actual operations**:
   - Scanner QR scan → Server lookup → Response
   - Verify repeater forwards real traffic
   - Check OLED shows production stats

4. **Monitor logs** for first few hours:
   ```bash
   tail -f log/repeater_200.log
   ```

## Related Documentation

- **CLAUDE.md** - Project overview and architecture
- **OLED_BATTERY_DISPLAY.md** - Repeater OLED display details
- **BATTERY_MONITORING_INA219.md** - Battery monitoring setup
- **REPEATER_SERVICE_SETUP.md** - Running repeater as system service

## Support

For issues during testing:
1. Check this troubleshooting guide
2. Review logs in `log/` directory
3. Verify hardware connections (antenna, OLED, power)
4. Test with nodes closer together to rule out range issues
5. Check frequency and node ID configurations

---

**Version**: 1.0
**Last Updated**: 2025
**Compatible With**: IQRight LoRa v2.0 (Binary Protocol)
