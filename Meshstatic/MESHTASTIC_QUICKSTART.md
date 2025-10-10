# Meshtastic Quick Start Guide

This is a condensed setup guide for getting the IQRight Meshtastic system running quickly.

## Prerequisites
- Raspberry Pi with SX1262 HAT (server and clients)
- ESP32 with LoRa module (optional repeaters)
- Python 3.8+

## Quick Setup (Raspberry Pi)

### 1. Enable SPI
```bash
echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt
echo "dtoverlay=spi0-0cs" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

### 2. Install Meshtastic
```bash
# Add repository
curl -fsSL https://download.opensuse.org/repositories/home:/meshtastic:/meshtastic/Raspbian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_meshtastic_meshtastic.gpg > /dev/null
echo 'deb http://download.opensuse.org/repositories/home:/meshtastic:/meshtastic/Raspbian_12/ /' | sudo tee /etc/apt/sources.list.d/meshtastic.list

# Install
sudo apt update
sudo apt install -y meshtasticd

# Install Python library
pip3 install meshtastic pypubsub
```

### 3. Configure Node

**SERVER (Node 1):**
```bash
sudo mkdir -p /etc/meshtasticd/config.d
sudo tee /etc/meshtasticd/config.d/config.yaml > /dev/null <<EOF
Lora:
  Module: sx1262
  DIO2_AS_RF_SWITCH: true
  CS: 21
  IRQ: 16
  Busy: 20
  Reset: 18
  Region: US
  ModemPreset: LONG_FAST

Config:
  Device:
    Role: ROUTER
    NodeId: 1
  Network:
    TCPEnabled: true
    TCPPort: 4403
EOF
```

**CLIENT (Node 102):**
```bash
sudo mkdir -p /etc/meshtasticd/config.d
sudo tee /etc/meshtasticd/config.d/config.yaml > /dev/null <<EOF
Lora:
  Module: sx1262
  DIO2_AS_RF_SWITCH: true
  CS: 21
  IRQ: 16
  Busy: 20
  Reset: 18
  Region: US
  ModemPreset: LONG_FAST

Config:
  Device:
    Role: CLIENT
    NodeId: 102
  Network:
    TCPEnabled: true
    TCPPort: 4403
EOF
```

**Note**: Change `NodeId: 102` to 103, 104, etc. for additional clients.

### 4. Start Service
```bash
sudo systemctl enable meshtasticd
sudo systemctl start meshtasticd
sudo systemctl status meshtasticd
```

### 5. Verify Connection
```bash
meshtastic --host localhost --info
```


## Quick ESP32 Repeater Setup

### 1. Flash Firmware
- Visit: https://flasher.meshtastic.org/
- Connect ESP32 via USB
- Select device model and flash

### 2. Configure via CLI
```bash
# Install CLI
pip3 install meshtastic

# Connect and configure
meshtastic --port /dev/ttyUSB0 --set lora.region US
meshtastic --port /dev/ttyUSB0 --set device.role ROUTER
meshtastic --port /dev/ttyUSB0 --set device.node_id 200
meshtastic --port /dev/ttyUSB0 --set lora.modem_preset LONG_FAST
```

### 3. Deploy
Power the ESP32 and place it midway between server and clients for optimal coverage.

## Verification Checklist

- [ ] SPI enabled (`ls /dev/spi*` shows devices)
- [ ] meshtasticd running (`systemctl status meshtasticd`)
- [ ] Config file correct (`cat /etc/meshtasticd/config.d/config.yaml`)
- [ ] Node visible (`meshtastic --host localhost --info`)
- [ ] Can send messages (`meshtastic --host localhost --sendtext "test" --dest 1`)
- [ ] Python can connect (no errors when running app)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Daemon won't start | Check SPI: `ls /dev/spi*` |
| Python can't connect | Verify: `netstat -tlnp \| grep 4403` |
| Messages not received | Check node IDs match in config.py |
| Low range | Switch to `LONG_SLOW` preset |

## Key Configuration Values

| Parameter | Server | Client | Repeater |
|-----------|--------|--------|----------|
| Role | ROUTER | CLIENT | ROUTER |
| Node ID | 1 | 102-199 | 200+ |
| Region | US | US | US |
| Modem | LONG_FAST | LONG_FAST | LONG_FAST |

## File Locations

- **Config**: `/etc/meshtasticd/config.d/config.yaml`
- **Logs**: `sudo journalctl -u meshtasticd -f`
- **Server App**: `CaptureMeshstatic.py`
- **Client App**: `scanner_meshstatic.py`
- **Settings**: `utils/config.py`

## Next Steps

1. Deploy server on main Raspberry Pi
2. Deploy clients on scanner stations
3. Add ESP32 repeaters as needed for coverage
4. Monitor mesh health: `meshtastic --host localhost --nodes`
5. Fine-tune modem preset based on range requirements

For detailed information, see `MESHTASTIC_SETUP.md`.
