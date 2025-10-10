# Meshtastic Implementation for IQRight Local Scanner System

This directory contains the Meshtastic mesh networking implementation for the IQRight Local scanner system, replacing the legacy direct LoRa communication with a self-healing mesh network.

## Overview

The Meshtastic implementation provides:
- **Extended Range**: Multi-hop mesh networking (2-5km per hop)
- **Reliability**: Self-healing network with automatic routing
- **Scalability**: Support for 10+ scanner nodes with ESP32 repeaters
- **Offline Capable**: Encrypted local credential storage with automatic GCP fallback
- **Security**: All credentials encrypted at rest

## Directory Structure


README.md                               ```This file```


data/                                   ```Encrypted data and key storage```
├── credentials.key                     ```Encryption key```
├── credentials.iqr                     ```Encrypted credentials```
├── full_load.iqr                       ```Encrypted user data```
└── offline_users.iqr                   ```Encrypted offline users```

docs/                                   ```System Documentation```
├── CREDENTIALS_SETUP.md                ```Security and credentials guide on Google Cloud and Locally```
├── MESHTASTIC_SETUP.md                 ```Complete setup guide```
└── MESHTASTIC_STROUBLESHOOTING.md      ```Testing and troubleshooting steps fpr Meshtastic```

logs/                                   **If this foolder doesn't exist, it should be created manually for the Web to run**

Meshstatic/
├── CaptureMeshstatic.py                ```Server application (receives scans)```
├── scanner_meshstatic.py               ```Client application (scanner stations)```
├── utils/
│   ├── config.py                       ```Configuration settings```
│   ├── api_client.py                   ```API communication with fallback```
│   ├── secure_credentials.py           ```Encrypted credential manager```
│   ├── credential_setup.py             ```Credential management CLI```
│   └── offline_data.py                 ```Offline data handling```

static/                                 ```Static files for the local web solution```
├── css                                 ```css for the local web solution```
├── dist                                ```dist for the local web solution```
├── images                              ```images for the local web solution```
├── js                                  ```js for the local web solution```
└── sounds                              **If this foolder doesn't exist, it should be created manually for the Web to run**

templates/                              ```Templates for the local web solution```

translations/                           ```Language flask-babel files for the local web solution```
├── es                                  ```Spanish language files for flask-babel```
└── pt                                  ```Portuguese language files for flask-babel```

utility_tests/                          ```Python and shell test scripts```

requirements.txt                        ```Python requirements file```



**Meshtastic Configuration**: See [MESHTASTIC_QUICKSTART.md](MESHTASTIC_QUICKSTART.md)

### 2. Setup Credentials

```bash
cd Meshstatic

# Generate encryption key
python3 utils/credential_setup.py --generate-key

# Sync from Google Cloud (if online)
python3 utils/credential_setup.py --sync-from-gcp

# OR add manually (if offline)
python3 utils/credential_setup.py --add apiUsername
python3 utils/credential_setup.py --add apiPassword
python3 utils/credential_setup.py --add mqttUsername
python3 utils/credential_setup.py --add mqttPassword
```

**Full Guide**: See [CREDENTIALS_SETUP.md](../docs/CREDENTIALS_SETUP.md)

### 3. Run Applications

**Server:**
```bash
python3 CaptureMeshstatic.py
```

**Client (Scanner):**
```bash
python3 scanner_meshstatic.py
```

## Key Features

### Secure Credential Management

- **Dual Storage**: Google Cloud Secret Manager (primary) + Encrypted Local Storage (fallback)
- **Automatic Fallback**: Seamlessly switches to local credentials when offline
- **Encryption**: All local credentials encrypted with Fernet (AES-128)
- **No Hardcoded Secrets**: All sensitive data stored securely

### Mesh Networking

- **Server**: Node ID 1, ROUTER role
- **Clients**: Node IDs 102+, CLIENT role
- **Repeaters**: ESP32 devices, Node IDs 200+, ROUTER role
- **Protocol**: Meshtastic with acknowledgments and automatic retries

### Offline Operation

The system is fully functional offline:
- Local encrypted user database
- Local encrypted credentials
- MQTT broker on localhost
- No internet dependency for core operations

## Configuration

Edit `utils/config.py` for:
- Node IDs (server/client)
- MQTT broker settings
- Meshtastic connection params
- File paths
- Facility settings

**Important**: Do NOT put credentials in config.py - use the encrypted credential system.

## Documentation

| Document                                                               | Purpose                                       |
|------------------------------------------------------------------------|-----------------------------------------------|
| [MESHTASTIC_SETUP.md](../docs/MESHTASTIC_SETUP.md)                     | Complete installation and configuration guide |
| [MESHTASTIC_TROUBLESHOOTING.md](../docs/MESHTASTIC_TROUBLESHOOTING.md) | Quick reference for setup commands            |
| [CREDENTIALS_SETUP.md](../docs/CREDENTIALS_SETUP.md)                   | Security and credential management guide      |

## Architecture

### Communication Flow

```
1. QR Scanner → Serial → scanner_meshstatic.py (Client RPi)
2. Client → Meshtastic Mesh → CaptureMeshstatic.py (Server RPi)
3. Server → Lookup user (API if online, local DB fallback)
4. Server → Meshtastic Mesh → Client (with user info)
5. Client → Display on GUI
6. Server → MQTT → Web Interface
```

### Network Topology

```
[Scanner 102] ←→ [ESP32 Repeater 200] ←→ [Server 1] → MQTT/API
[Scanner 103] ←→ [ESP32 Repeater 201] ←→ [Server 1] → MQTT/API
```

- Clients communicate only with server (star topology via mesh)
- Repeaters extend range automatically
- Mesh routing handles multi-hop automatically

```
┌─────────────────────────────────────────────────────────────┐
│                     Mesh Network Topology                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Scanner Client (Node 102)                                  │
│  ┌──────────────────┐                                       │
│  │ RPi + SX1262     │                                       │
│  │ scanner_meshstatic.py                                    │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           │ (Meshtastic Mesh)                               │
│           ▼                                                 │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ ESP32 Repeater   │◄────────┤ ESP32 Repeater   │          │
│  │ (Node 200)       │         │ (Node 201)       │          │
│  │ ROUTER role      │         │ ROUTER role      │          │
│  └────────┬─────────┘         └─────────┬────────┘          │
│           │                             │                   │
│           └──────────┬──────────────────┘                   │
│                      ▼                                      │
│           ┌──────────────────┐                              │
│           │ Server (Node 1)  │                              │
│           │ RPi + SX1262     │                              │
│           │ CaptureMeshstatic.py                            │
│           └────────┬─────────┘                              │
│                    │                                        │
│                    ├──► MQTT Broker (localhost)             │
│                    └──► API Server (cloud)                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Hardware Requirements

### Server
- Raspberry Pi 3/4/5
- SX1262 LoRa HAT (915MHz US / 868MHz EU)
- Power supply
- Network connection (for MQTT and API)

### Clients
- Raspberry Pi 3/4/5
- SX1262 LoRa HAT
- QR Scanner (serial)
- Touchscreen display
- Power supply

### Repeaters (Optional)
- ESP32 with SX1262 module
  - Heltec LoRa 32 V3
  - TTGO T-Beam
  - LilyGO devices
- Power supply or battery

## Dependencies

```bash
pip install -r requirements.txt
```

Key packages:
- `meshtastic>=2.3.0` - Mesh networking
- `pypubsub>=4.0.3` - Event system
- `cryptography` - Credential encryption
- `google-cloud-secret-manager` - GCP integration
- `paho-mqtt` - MQTT communication
- `aiohttp` - Async HTTP
- `pandas` - Data processing

## Development

### Local Testing

```bash
# Set environment for local mode
export LOCAL=TRUE
export LORASERVICE_PATH=.

# Run without hardware
python3 CaptureMeshstatic.py
```

### Adding New Credentials

```python
from utils.secure_credentials import get_credentials_manager

manager = get_credentials_manager()
manager.set_local_secret('newCredential', 'value')
```

### Testing Offline Mode

```python
from utils.secure_credentials import get_credentials_manager

manager = get_credentials_manager()
manager.force_offline_mode()

# All credential requests now use local storage
result = manager.get_secret('apiUsername')
```

## Security

### Credential Storage

- **GCP Secrets**: Stored in Google Cloud Secret Manager (primary)
- **Local Secrets**: Encrypted with Fernet (AES-128) in `data/credentials.iqr`
- **Encryption Key**: Stored in `data/credentials.key` (600 permissions)

### Best Practices

1. **Backup** encryption key securely (separate from credentials)
2. **Permissions**: Set 600 on all credential files
3. **Rotation**: Sync from GCP periodically
4. **Monitoring**: Review access logs regularly
5. **No Git**: Credential files are gitignored

## Changelog

### v2.0.0 (Current)
- ✅ Meshtastic mesh networking
- ✅ Encrypted credential storage
- ✅ Automatic GCP/local fallback
- ✅ Offline operation support
- ✅ ESP32 repeater support

### v1.0.0 (Legacy)
- Direct LoRa communication
- GCP-only credentials
- Point-to-point only

## Support

For issues or questions:
1. Review documentation in this directory
2. Check logs: `tail -f log/IQRight_Daemon.debug`
3. Verify configuration: `python3 utils/credential_setup.py --list`
4. Test connectivity: `meshtastic --host localhost --info`
5. Consult troubleshooting guides

## License

Proprietary - IQRight, Inc.

## Authors

- Original LoRa Implementation: IQRight Development Team
- Meshtastic Migration: Claude + IQRight Team (2025)
