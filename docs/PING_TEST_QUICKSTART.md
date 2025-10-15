# LoRa Ping Test - Quick Start

One-page reference for positioning repeaters using ping tests.

## Setup

### On Server (Node 1)
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate
python3 test_ping_server.py
```

### On Scanner (Node 100-199)
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate
LORA_NODE_ID=102 python3 test_ping_scanner.py
```
Click **"Start Ping Test"** in GUI

### On Repeater (Node 200-256)
```bash
cd /Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local
source .venv/bin/activate
LORA_NODE_ID=200 python3 test_ping_repeater.py
```

## Signal Strength Guide

| RSSI | Quality | Action |
|------|---------|--------|
| ≥ -70 dBm | EXCELLENT | No repeater needed |
| -70 to -85 dBm | GOOD | Repeater optional |
| -85 to -100 dBm | FAIR | Repeater recommended |
| < -100 dBm | POOR | Repeater required |

## Positioning Steps

1. **Test Direct Connection**
   - Run server + scanner scripts
   - Check RSSI on scanner GUI
   - If RSSI < -85 dBm → Need repeater

2. **Position Repeater**
   - Start repeater near server
   - Slowly move toward scanner
   - Watch OLED RSSI values
   - Stop when both directions show GOOD signal

3. **Verify**
   - Scanner GUI shows "Via Repeater"
   - Success rate ≥ 90%
   - Repeater OLED shows both PING and PONG

## What to Watch

### Scanner GUI
- **RSSI**: Current signal strength
- **Success Rate**: % of PONGs received (target: ≥ 90%)
- **Via Repeater**: Count of responses through repeater

### Repeater OLED
```
┌────────────────────────────┐
│ PING TEST                  │
│────────────────────────────│
│ Last: PING 102->1          │ ← Last packet
│ RSSI: -65 dBm (GOOD)       │ ← Signal strength
│ ──────────────────────────│
│ PING>: 15  PONG<: 14       │ ← Forwarding counts
│ Tot: 29  Drop: 0           │ ← Total/dropped
│ Avg: -68 dBm               │ ← Average RSSI
└────────────────────────────┘
```

### Server Console
- Shows RSSI from scanner
- Shows if packet came direct or via repeater

## Stop Tests

- **Scanner**: Click "Stop Test" then "Quit"
- **Server/Repeater**: Press Ctrl+C

## Troubleshooting

**No PONGs received?**
- Check server is running
- Verify frequency matches (check .env)
- Move scanner closer to server

**Repeater not forwarding?**
- Check repeater node ID (200-256)
- Move repeater closer to scanner or server
- Verify OLED shows activity

**Poor RSSI despite close range?**
- Check antenna connections
- Try different antenna orientation
- Move away from metal structures

## Complete Guide

For detailed documentation, see: `docs/PING_TEST_GUIDE.md`

---

**Quick Reference Card** | IQRight LoRa v2.0
