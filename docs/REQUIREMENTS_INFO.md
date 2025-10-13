# Python Requirements by Node Type

This document explains the minimal, node-specific Python requirements for the IQRight LoRa system.

## Philosophy

Each node type has its own requirements file containing **only what that specific node needs**. This:
- Minimizes installation time
- Reduces storage requirements (important for Pi Zero)
- Prevents unnecessary dependencies
- Makes deployment cleaner

## Requirements Files Location

All requirements files are in the `configs/` directory:

```
configs/
├── requirements.server.txt    # Server (CaptureLora.py + mqtt_grid_web.py)
├── requirements.scanner.txt   # Scanner (scanner_queue.py)
└── requirements.repeater.txt  # Repeater (repeater.py)
```

## Server Requirements (`requirements.server.txt`)

**Applications**: CaptureLora.py, mqtt_grid_web.py

### Core Dependencies
- `python-dotenv` - Environment variable management
- `pandas` - Data processing
- `cryptography` - Decrypt .iqr files

### Communication
- `paho-mqtt` - MQTT broker communication
- `aiohttp` - Async HTTP for API calls

### Hardware
- `adafruit-circuitpython-rfm9x` - RFM9x LoRa radio
- `adafruit-blinka` - CircuitPython compatibility layer

### Web Interface
- `flask` - Web server for mqtt_grid_web.py

### Optional
- `google-cloud-secret-manager` - Cloud secret management

**Total**: ~8 packages

## Scanner Requirements (`requirements.scanner.txt`)

**Application**: scanner_queue.py

### Core Dependencies
- `python-dotenv` - Environment variable management
- `pandas` - Data processing (teacher mapping)
- `cryptography` - Decrypt .iqr files

### GUI
- `tksheet` - Spreadsheet widget for Tkinter
- **Note**: Tkinter itself is built into Python on most systems

### Hardware
- `adafruit-circuitpython-rfm9x` - RFM9x LoRa radio
- `adafruit-blinka` - CircuitPython compatibility layer
- `pyserial` - QR scanner serial communication
- `RPi.GPIO` - GPIO control for scanner hardware

**Total**: ~7 packages

## Repeater Requirements (`requirements.repeater.txt`)

**Application**: repeater.py

### Core Dependencies
- `python-dotenv` - Environment variable management

### Hardware
- `adafruit-circuitpython-rfm9x` - RFM9x LoRa radio
- `adafruit-blinka` - CircuitPython compatibility layer

### Display
- `adafruit-circuitpython-ssd1306` - OLED display driver
- `pillow` - Image processing for display

**Total**: ~5 packages

## Comparison

| Dependency       | Server | Scanner | Repeater |
|------------------|--------|---------|--------|
| python-dotenv    | ✓      | ✓       | ✓      |
| pandas           | ✓      | ✓       | ✗      |
| cryptography     | ✓      | ✓       | ✗      |
| paho-mqtt        | ✓      | ✗       | ✗      |
| aiohttp          | ✓      | ✗       | ✗      |
| flask            | ✓      | ✗       | ✗      |
| tksheet          | ✗      | ✓       | ✗      |
| pyserial         | ✗      | ✓       | ✗      |
| RPi.GPIO         | ✗      | ✓       | ✗      |
| adafruit-rfm9x   | ✓      | ✓       | ✓      |
| adafruit-blinka  | ✓      | ✓       | ✓      |
| adafruit-ssd1306 | ✗      | ✗       | ✓      |
| pillow           | ✗      | ✗       | ✓      |

## Installation

### Automatic (Recommended)

Run the setup script which automatically installs the correct requirements:

```bash
./setup.sh
```

### Manual

If you need to install manually:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install for your node type
pip install -r configs/requirements.server.txt    # Server
pip install -r configs/requirements.scanner.txt   # Scanner
pip install -r configs/requirements.repeater.txt  # Repeater
```

## Hardware-Specific Notes

### Raspberry Pi

All hardware libraries (Adafruit, GPIO) are Raspberry Pi specific. They will fail to install on Mac/Linux unless you set `LOCAL=TRUE` in `.env` for testing.

### Development/Testing

For testing without hardware on Mac/Linux:

1. Create a minimal requirements file:
   ```bash
   cat > requirements.dev.txt << EOF
   python-dotenv>=1.0.0
   pandas>=2.0.0
   cryptography>=41.0.0
   EOF
   ```

2. Install:
   ```bash
   pip install -r requirements.dev.txt
   ```

3. Run with:
   ```bash
   export LOCAL=TRUE
   python scanner_queue.py
   ```

## Package Size Comparison

Approximate installed sizes:

| Node Type | Package Count | Approx. Size |
|-----------|---------------|--------------|
| Server    | ~8            | ~150 MB      |
| Scanner   | ~7            | ~120 MB      |
| Repeater  | ~3-5          | ~60-80 MB    |

**Note**: Repeater has the smallest footprint, making it ideal for Pi Zero with limited storage.

## Troubleshooting

### Installation Failures

**Problem**: Hardware packages fail to install on non-Pi systems

**Solution**: Don't install on Mac/Linux for development. Use `LOCAL=TRUE` mode instead.

---

**Problem**: "No module named 'RPi'"

**Solution**: This is Raspberry Pi specific. Either:
- Run on actual Raspberry Pi hardware
- Set `LOCAL=TRUE` for testing

---

**Problem**: Package compilation errors

**Solution**: Install system dependencies first:
```bash
sudo apt-get update
sudo apt-get install python3-dev python3-pip build-essential
```

### Version Conflicts

If you get version conflicts between packages:

1. Delete virtual environment:
   ```bash
   rm -rf .venv
   ```

2. Re-run setup:
   ```bash
   ./setup.sh
   ```

## Updating Requirements

To update dependencies:

1. Edit the appropriate file in `configs/`
2. Re-run installation:
   ```bash
   pip install -r configs/requirements.server.txt  # or scanner/repeater
   ```
