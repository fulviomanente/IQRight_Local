# IQRight LoRa Setup Guide

## Quick Setup

Run the interactive setup script with automatic virtual environment handling:

```bash
./setup.sh
```

Or if you already have a virtual environment activated:

```bash
python setup.py
```

The setup script will:
1. Ask you to choose node type (Server, Scanner, or Repeater)
2. Ask you to specify a node ID
3. Create necessary directories (`log/`, `data/`)
4. Copy `.iqr` data files to `data/` directory
5. Install the appropriate config file to `utils/config.py`
6. Create `.env` file with your node ID
7. Install node-specific Python dependencies

**Note**: `setup.sh` automatically creates/activates a virtual environment before running setup.

## Node Types and IDs

### 1. Server (Node ID: 1)
- **Node ID**: Always `1`
- **Purpose**: Main receiver and data processor
- **Config**: `configs/config.server.py`
- **Run with**: `python CaptureLora.py`

### 2. Scanner (Node ID: 100-199)
- **Node ID Range**: `100-199`
- **Purpose**: QR code scanner devices
- **Config**: `configs/config.scanner.py`
- **Run with**: `python scanner_queue.py`
- **Example IDs**:
  - 102 (Gym Side)
  - 103 (East Side)

### 3. Repeater (Node ID: 200-256)
- **Node ID Range**: `200-256`
- **Purpose**: Extends LoRa network range
- **Config**: `configs/config.repeater.py`
- **Run with**: `python repeater.py`
- **Example IDs**: 200, 201, 202

## Manual Setup

If you prefer to set up manually:

### 1. Create directories
```bash
mkdir -p log data
```

### 2. Copy data files
```bash
cp *.iqr data/
cp offline.key data/
```

### 3. Copy config file
```bash
# For Server:
cp configs/config.server.py utils/config.py

# For Scanner:
cp configs/config.scanner.py utils/config.py

# For Repeater:
cp configs/config.repeater.py utils/config.py
```

### 4. Create .env file
```bash
cat > .env << EOF
LORA_NODE_ID=102
LORA_FREQUENCY=915.23
LORA_TX_POWER=23
LORA_ENABLE_CA=TRUE
EOF
```

## Directory Structure

After setup:

```
IQRight_Local/
├── configs/
│   ├── config.server.py           # Server configuration
│   ├── config.scanner.py          # Scanner configuration
│   ├── config.repeater.py         # Repeater configuration
│   ├── requirements.server.txt    # Server Python dependencies
│   ├── requirements.scanner.txt   # Scanner Python dependencies
│   └── requirements.repeater.txt  # Repeater Python dependencies
├── data/
│   ├── *.iqr                      # Encrypted data files
│   └── offline.key                # Encryption key
├── log/
│   ├── IQRight_Server.debug
│   ├── IQRight_Scanner.debug
│   └── repeater_*.log
├── utils/
│   └── config.py                  # Active configuration (copied from configs/)
├── .venv/ or venv/                # Python virtual environment
├── .env                           # Node ID and settings
├── setup.sh                       # Setup script with venv handling
├── setup.py                       # Interactive setup (Python)
├── CaptureLora.py                 # Server application
├── scanner_queue.py               # Scanner application
└── repeater.py                    # Repeater application
```

## Configuration Files

### utils/config.py
The **active** configuration file used by the application. This is automatically copied from `configs/` during setup.

### configs/*.py
Template configuration files for each node type. These are **source** files - the setup script copies the appropriate one to `utils/config.py`.

### .env
Environment variables for node-specific settings:
- `LORA_NODE_ID`: Your unique node ID
- `LORA_FREQUENCY`: LoRa frequency (default: 915.23 MHz)
- `LORA_TX_POWER`: Transmission power (default: 23 dBm)
- `LORA_ENABLE_CA`: Collision avoidance (TRUE/FALSE)
- `LOCAL`: Set to TRUE for testing without hardware

## Running the Applications

**Important**: Always activate the virtual environment first!

```bash
source .venv/bin/activate  # or: source venv/bin/activate
```

### Server
```bash
python CaptureLora.py
```

### Scanner
```bash
python scanner_queue.py
```

### Repeater
```bash
python repeater.py
```

## Python Dependencies

Each node type has minimal, specific requirements in `configs/`:

### Server (`requirements.server.txt`)
- Core: python-dotenv, pandas, cryptography
- MQTT: paho-mqtt
- API: aiohttp
- LoRa: adafruit-circuitpython-rfm9x, adafruit-blinka
- Web: flask
- Cloud: google-cloud-secret-manager (optional)

### Scanner (`requirements.scanner.txt`)
- Core: python-dotenv, pandas, cryptography
- GUI: tksheet
- LoRa: adafruit-circuitpython-rfm9x, adafruit-blinka
- Hardware: pyserial, RPi.GPIO

### Repeater (`requirements.repeater.txt`)
- Core: python-dotenv
- LoRa: adafruit-circuitpython-rfm9x, adafruit-blinka
- Display: adafruit-circuitpython-ssd1306, pillow (optional)

### Manual Installation

If automatic installation fails:

```bash
source .venv/bin/activate

# Server
pip install -r configs/requirements.server.txt

# Scanner
pip install -r configs/requirements.scanner.txt

# Repeater
pip install -r configs/requirements.repeater.txt
```

## Testing Without Hardware

For development/testing on Mac/Linux without LoRa hardware:

```bash
export LOCAL=TRUE
python scanner_queue.py  # or CaptureLora.py
```

## Network Configuration

### Node ID Allocation
- **Server**: `1` (fixed)
- **Scanners**: `100-199` (assign unique ID to each scanner)
- **Repeaters**: `200-256` (assign unique ID to each repeater)

### Example Network
```
Server (1)
├── Scanner 102 (Gym Side)
├── Scanner 103 (East Side)
└── Repeater 200
    ├── Scanner 104 (Far Location)
    └── Scanner 105 (Far Location)
```

## Troubleshooting

### Setup fails to create directories
- Check write permissions in the current directory
- Run with `sudo` if needed

### No .iqr files found
- Make sure `.iqr` data files are in the project root before running setup
- You can manually copy files to `data/` after setup

### Config not working
- Verify `utils/config.py` exists
- Check that `.env` file has correct `LORA_NODE_ID`
- Review logs in `log/` directory

### HELLO handshake fails
- Verify server is running first
- Check node IDs are unique
- Ensure LoRa hardware is connected
- Review server logs: `tail -f log/IQRight_Server.debug`
- Review scanner logs: `tail -f log/IQRight_Scanner.debug`

## Re-running Setup

You can re-run setup anytime to:
- Change node type
- Change node ID
- Reconfigure the device

The setup script will backup your existing `utils/config.py` to `config.py.backup`.

## Support

For issues or questions:
- Check logs in `log/` directory
- Review OLED_SETUP.md for repeater display setup
- See CLAUDE.md for development guidelines
