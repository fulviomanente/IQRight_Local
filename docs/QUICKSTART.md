# IQRight LoRa Quick Start

## Setup (One Time)

```bash
./setup.sh
```

Follow prompts:
1. Select node type (1=Server, 2=Scanner, 3=Repeater)
2. Enter node ID
3. Confirm setup

**Done!** The script creates directories, copies configs, installs dependencies.

---

## Running

### Activate Virtual Environment
```bash
source .venv/bin/activate  # or: source venv/bin/activate
```

### Start Application

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
python repeater.py
```

---

## Node ID Ranges

| Type | ID Range | Default |
|------|----------|---------|
| Server | 1 (fixed) | 1 |
| Scanner | 100-199 | 102 |
| Repeater | 200-256 | 200 |

---

## Files Created

```
configs/           # Node-specific configs & requirements
data/              # Encrypted data files (.iqr)
log/               # Application logs
utils/config.py    # Active config (auto-selected)
.env               # Node ID and settings
.venv/             # Virtual environment
```

---

## Troubleshooting

### HELLO Handshake Fails

**Scanner shows "Server Handshake Failed!"**

1. Check server is running
2. Check node IDs are unique
3. Click **Reset** button to retry
4. Move closer to server/repeater

**Check logs:**
```bash
tail -f log/IQRight_Server.debug   # Server
tail -f log/IQRight_Scanner.debug  # Scanner
tail -f log/repeater_*.log         # Repeater
```

### No LoRa Hardware

**For testing on Mac/Linux without hardware:**

```bash
export LOCAL=TRUE
python scanner_queue.py  # or other app
```

### Re-run Setup

To change node type or ID:

```bash
./setup.sh
```

Old config backed up to `utils/config.py.backup`

---

## Complete Documentation

- **SETUP_README.md** - Full setup guide
- **REQUIREMENTS_INFO.md** - Python dependencies explained
- **OLED_SETUP.md** - Repeater OLED display setup
- **CLAUDE.md** - Development guidelines

---

## Quick Commands

```bash
# Setup
./setup.sh

# Activate venv
source .venv/bin/activate

# Run (choose one)
python CaptureLora.py      # Server
python scanner_queue.py    # Scanner
python repeater.py         # Repeater

# Check logs
tail -f log/*.debug
tail -f log/repeater_*.log

# Manual install requirements
pip install -r configs/requirements.server.txt    # Server
pip install -r configs/requirements.scanner.txt   # Scanner
pip install -r configs/requirements.repeater.txt  # Repeater
```

---

## Network Example

```
Server (Node 1)
  |
  ├─ Scanner 102 (Gym Side)
  ├─ Scanner 103 (East Side)
  └─ Repeater 200
       ├─ Scanner 104 (Far Location)
       └─ Scanner 105 (Far Location)
```

Each node runs independently with its own config and minimal dependencies.
