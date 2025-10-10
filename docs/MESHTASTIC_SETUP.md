# Meshtastic Setup Guide for IQRight Local Scanner System

This guide provides step-by-step instructions for setting up the Meshtastic mesh networking system for the IQRight Local scanner infrastructure.

## Table of Contents
- [Overview](#overview)
- [Hardware Requirements](#hardware-requirements)
- [Installation Steps](#installation-steps)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Troubleshooting](#troubleshooting)

## Overview

The Meshtastic implementation replaces the direct LoRa communication with a mesh networking approach that provides:
- **Extended Range**: ESP32 repeaters create a self-healing mesh network
- **Better Reliability**: Automatic routing and message retries
- **Scalability**: Easy to add more nodes and repeaters
- **Community Support**: Active open-source development and features

## Hardware Requirements

### Server (Main Receiver)
- Raspberry Pi (3, 4, or 5)
- SX1262 LoRa HAT (915MHz for US, 868MHz for EU)
- Power supply
- Internet connection (for API and MQTT)

### Client (Scanner Stations)
- Raspberry Pi (3, 4, or 5)
- SX1262 LoRa HAT
- QR Code Scanner (connected via serial)
- Touchscreen display (for GUI)
- Power supply

### Repeaters (Mesh Nodes)
- ESP32 board with SX1262 LoRa module
  - Examples: Heltec LoRa 32 V3, TTGO T-Beam, LilyGO T-Echo
- Battery or power supply
- Optional: Enclosure for outdoor deployment

## Installation Steps

### 1. Prepare Raspberry Pi (Server and Clients)

#### 1.1 Enable SPI
Edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older systems):
```bash
sudo nano /boot/firmware/config.txt
```

Add these lines:
```
dtparam=spi=on
dtoverlay=spi0-0cs
```

Reboot:
```bash
sudo reboot
```

#### 1.2 Install Meshtastic Daemon 
(Source: https://meshtastic.org/docs/hardware/devices/linux-native-hardware/)

Add the Meshtastic repository:
```bash
[[ "$(. /etc/os-release && echo $NAME)" == Raspbian* ]] && echo "ERROR: Raspberry Pi OS (32-bit) detected, please use the Raspbian repos."
echo 'deb http://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_12/ /' | sudo tee /etc/apt/sources.list.d/network:Meshtastic:beta.list
curl -fsSL https://download.opensuse.org/repositories/network:Meshtastic:beta/Debian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/network_Meshtastic_beta.gpg > /dev/null
```

Install meshtasticd:
```bash
sudo apt update
sudo apt install -y meshtasticd
```

#### 1.4 Install Python Dependencies
```bash
cd /etc/iqright/LoraService
source venv/bin/activate
pip3 install meshtastic pypubsub
```

### 2. Configure Meshtastic Daemon

#### 2.1 General Configuration

Check the existance of  `/etc/meshtasticd/config.d/config.yaml`:
**Note**: For Raspberry Pi 5 server , add `gpiochip: 4` to the Lora section.

# Check all available yaml config files
ls /etc/meshtasticd/available.d

# Then, copy the right config to `config.d`
sudo cp /etc/meshtasticd/available.d/lora-waveshare-sxxx.yaml /etc/meshtasticd/config.d/.

Insert the specific config for the node into `/etc/meshtasticd/config.d/lora-waveshare-sxxx.yaml`:
sudo nano /etc/meshtasticd/config.d/lora-waveshare-sxxx.yaml

**Note**: From here, follow 2.2 for server and 2.3 for Scanners

#### 2.2 Server Configuration (Node 1) - Server

# DO NOT TOUCH THIS PIECE OF THE YAML 
Lora:
  Module: sx1262
  DIO2_AS_RF_SWITCH: true
  CS: 21
  IRQ: 16
  Busy: 20
  Reset: 18
######################################  
# Copy from next line on, to the yaml file 
  Region: US
  ModemPreset: LONG_FAST

# Node configuration
Config:
  Device:
    Role: ROUTER  # Server acts as router for mesh
    NodeId: 1

  Network:
    WiFiEnabled: true
    EthEnabled: false
    TCPEnabled: true
    TCPPort: 4403

  # Serial and TCP interfaces
  Serial:
    Enabled: true
    Baud: 115200

  Region: US
  ModemPreset: LONG_FAST
#######################################


#### 2.3 Client Configuration (Node 102, 103, etc.) - For each Scanner

# DO NOT TOUCH THIS PIECE OF THE YAML 
Lora:
  Module: sx1262
  DIO2_AS_RF_SWITCH: true
  CS: 21
  IRQ: 16
  Busy: 20
  Reset: 18
######################################  
# Copy from next line on, to the yaml file 
  Region: US
  ModemPreset: LONG_FAST

Config:
  Device:
    Role: CLIENT  # Client role for scanners
    NodeId: 102  # Change per device: 102, 103, 104, etc.

  Network:
    TCPEnabled: true
    TCPPort: 4403
#######################################

#### 2.4 Set Permissions
```bash
sudo chown -R meshtasticd:meshtasticd /etc/meshtasticd
sudo chmod 644 /etc/meshtasticd/config.d/lora-waveshare-sxxx.yaml
```
### 4. Create and Start Meshtastic Services

#### 4.1 Create the Service

```bash
sudo nano /etc/systemd/system/meshtasticd.service
```

#Paste the content into the meshtasticd.service file
[Unit]
Description=Meshtastic Daemon
After=network.target

[Service]
ExecStart=/usr/bin/meshtasticd
Restart=always
User=root
Group=root
Type=simple

[Install]
WantedBy=multi-user.target


#### 4.1 Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable meshtasticd
sudo systemctl start meshtasticd
```

#### 4.2 Check Status
```bash
sudo systemctl status meshtasticd
```

#### 4.3 View Logs
```bash
sudo journalctl -u meshtasticd -f
```

### 5. Update Application Configuration

Edit `utils/config.py` on each device:

**Server (Node 1):**
```python
MESHTASTIC_SERVER_NODE_ID = 1
MESHTASTIC_CLIENT_NODE_ID = 102  # Not used on server
```

**Client (Node 102):**
```python
MESHTASTIC_SERVER_NODE_ID = 1
MESHTASTIC_CLIENT_NODE_ID = 102  # Change per device
```

### 6. Configure ESP32 Repeaters

For ESP32 repeaters, you don't need custom code - just flash the official Meshtastic firmware:

#### 6.1 Install Meshtastic Firmware
1. Go to https://flasher.meshtastic.org/
2. Connect ESP32 to computer via USB
3. Select your device model
4. Flash the latest stable firmware

#### 6.2 Configure via Web Interface
```bash
# Install Meshtastic CLI on your laptop
pip3 install meshtastic

# Connect to device via serial
meshtastic --port /dev/ttyUSB0

# Or via Bluetooth
meshtastic --ble "Device Name"
```

Set the configuration:
```bash
# Set region
meshtastic --set lora.region US

# Set role to ROUTER
meshtastic --set device.role ROUTER

# Set node ID (200, 201, etc.)
meshtastic --set device.node_id 200

# Set modem preset for range
meshtastic --set lora.modem_preset LONG_FAST

# Enable position broadcast (optional)
meshtastic --set position.gps_enabled false
```

## Running the System

### Server
```bash
cd /path/to/IQRight_Local
python3 CaptureMeshstatic.py
```

### Client (Scanner)
```bash
cd /path/to/IQRight_Local
python3 scanner_meshstatic.py
```

### Autostart with systemd

Create `/etc/systemd/system/iqright-server.service`:
```ini
[Unit]
Description=IQRight Meshtastic Server
After=network.target meshtasticd.service
Requires=meshtasticd.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/IQRight_Local
ExecStart=/usr/bin/python3 /home/pi/IQRight_Local/CaptureMeshstatic.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable iqright-server
sudo systemctl start iqright-server
```

## Testing the System

### 1. Verify Meshtastic Connectivity

On server:
```bash
meshtastic --host localhost --info
```

Expected output should show node information and connected nodes.

### 2. Test Message Sending

From client:
```bash
meshtastic --host localhost --sendtext "Test message" --dest 1
```

Check server logs for received message.

### 3. Monitor Mesh Network

```bash
# View all nodes in mesh
meshtastic --host localhost --nodes

# Monitor messages
meshtastic --host localhost --listen
```

## Troubleshooting

### Meshtastic daemon won't start

**Check SPI:**
```bash
ls /dev/spi*
# Should show: /dev/spidev0.0  /dev/spidev0.1
```

**Check GPIO permissions:**
```bash
sudo usermod -a -G gpio,spi meshtasticd
```

**Check logs:**
```bash
sudo journalctl -u meshtasticd -n 100
```

### Python app can't connect to daemon

**Verify daemon is listening:**
```bash
sudo netstat -tlnp | grep 4403
```

**Test TCP connection:**
```bash
telnet localhost 4403
```

### Messages not reaching destination

**Check node IDs:**
```bash
meshtastic --host localhost --info
```

Verify node IDs match configuration.

**Check mesh topology:**
```bash
meshtastic --host localhost --nodes
```

All nodes should appear in the list.

**Check signal strength:**
```bash
meshtastic --host localhost --listen
```

Look for SNR and RSSI values in received packets.

### High latency or packet loss

**Adjust modem preset:**
- `LONG_FAST`: Good balance (recommended)
- `LONG_SLOW`: Maximum range, slower
- `MEDIUM_FAST`: Faster, shorter range

```bash
meshtastic --host localhost --set lora.modem_preset LONG_SLOW
```

**Check for interference:**
- Move away from WiFi routers
- Avoid metal obstructions
- Elevate antennas

### ESP32 repeater not joining mesh

**Verify firmware version:**
All devices should run the same major version.

**Check region setting:**
All nodes must use the same region (US, EU_868, etc.)

**Reset to defaults:**
```bash
meshtastic --port /dev/ttyUSB0 --factory-reset
```

## Security Considerations

By default, Meshtastic messages are **unencrypted** within the mesh. For production:

1. **Enable encryption:**
```bash
meshtastic --set security.public_key false
meshtastic --set security.private_key <your-key>
```

2. **Use channels:**
```bash
meshtastic --ch-set name "IQRight"
meshtastic --ch-set psk <encryption-key>
```

3. **Restrict to specific nodes:**
Configure client roles to prevent unauthorized nodes from joining.

## Support and Resources

- **Meshtastic Docs**: https://meshtastic.org/docs/
- **Python API**: https://python.meshtastic.org/
- **Community**: https://meshtastic.discourse.group/
- **GitHub**: https://github.com/meshtastic/

## Maintenance

### Update Firmware
```bash
# Update meshtasticd
sudo apt update
sudo apt upgrade meshtasticd

# Update Python library
pip3 install --upgrade meshtastic
```

### Backup Configuration
```bash
sudo cp -r /etc/meshtasticd/config.d ~/meshtastic-backup-$(date +%Y%m%d)
```

### Monitor Health
```bash
# Check daemon status
sudo systemctl status meshtasticd

# Check application logs
tail -f /path/to/IQRight_Daemon.debug

# Check mesh nodes
meshtastic --host localhost --nodes
```
