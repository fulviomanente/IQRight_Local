# Meshtastic Test Guide for IQRight Local Scanner System

This guide provides step-by-step instructions for testing Meshtastic mesh networking system for the IQRight Local infrastructure.
Make sure all steps from MESHTASTIC_SETUP.md were properly executed before testing it

## Table of Contents
- [Summary](#summary)
- [Testing the System](#testing the System)
- [Troubleshooting](#troubleshooting)
- [Hardware Requirements](#hardware-requirements)

## Summary

### Verification Checklist

- [ ] SPI enabled (`ls /dev/spi*` shows devices)
- [ ] meshtasticd running (`systemctl status meshtasticd`)
- [ ] Config file correct (`cat /etc/meshtasticd/config.d/config.yaml`)
- [ ] Node visible (`meshtastic --host localhost --info`)
- [ ] Can send messages (`meshtastic --host localhost --sendtext "test" --dest 1`)
- [ ] Python can connect (no errors when running app)

### Quick Troubleshooting

| Problem               | Solution                             |
|-----------------------|--------------------------------------|
| Daemon won't start    | Check SPI: `ls /dev/spi*`            |
| Python can't connect  | Verify: `netstat -tlnp \| grep 4403` |
| Messages not received | Check node IDs match in config.py    |
| Low range             | Switch to `LONG_SLOW` preset         |

### Key Configuration Values

| Parameter | Server    | Client    | Repeater  |
|-----------|-----------|-----------|-----------|
| Role      | ROUTER    | CLIENT    | ROUTER    |
| Node ID   | 1         | 102-199   | 200+      |
| Region    | US        | US        | US        |
| Modem     | LONG_FAST | LONG_FAST | LONG_FAST |

### File Locations

- **Config**: `/etc/meshtasticd/config.d/config.yaml`
- **Logs**: `sudo journalctl -u meshtasticd -f`
- **Server App**: `CaptureMeshstatic.py`
- **Client App**: `scanner_meshstatic.py`
- **Settings**: `utils/config.py`


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

```