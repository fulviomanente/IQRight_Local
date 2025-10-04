# Migration Guide: LoRa to Meshtastic

This guide helps you migrate from the legacy LoRa implementation to the new Meshtastic mesh networking system.

## Overview

The migration involves:
1. Installing Meshtastic daemon on Raspberry Pi devices
2. Configuring SX1262 HAT pins
3. Switching from direct LoRa communication to mesh networking
4. Updating application code to use new files

## Key Changes

### Architecture Changes

| Aspect | Old (LoRa) | New (Meshtastic) |
|--------|-----------|-----------------|
| **Files** | `CaptureLora.py`, `scanner_queue.py` | `CaptureMeshstatic.py`, `scanner_meshstatic.py` |
| **Hardware** | RFM9x module | SX1262 HAT |
| **Communication** | Direct SPI to hardware | TCP to meshtasticd daemon |
| **Protocol** | Point-to-point | Mesh network |
| **Range** | Single hop | Multi-hop via repeaters |
| **Routing** | Manual | Automatic |

### Code Changes

#### Server Side

**Old (CaptureLora.py):**
```python
import adafruit_rfm9x
rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RFM9X_FREQUENCE)
packet = rfm9x.receive(with_ack=True, with_header=True)
rfm9x.send_with_ack(bytes(msg, "UTF-8"))
```

**New (CaptureMeshstatic.py):**
```python
import meshtastic.tcp_interface
from pubsub import pub

mesh_interface = meshtastic.tcp_interface.TCPInterface(hostname='localhost')
pub.subscribe(onReceive, "meshtastic.receive.text")
mesh_interface.sendText(text=msg, destinationId=node_id, wantAck=True)
```

#### Client Side

**Old (scanner_queue.py):**
```python
self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ)
self.rfm9x.send_with_ack(bytes(payload, "UTF-8"))
packet = self.rfm9x.receive(with_header=True)
```

**New (scanner_meshstatic.py):**
```python
self.mesh = meshtastic.tcp_interface.TCPInterface(hostname='localhost')
pub.subscribe(self.onReceive, "meshtastic.receive.text")
self.mesh.sendText(text=payload, destinationId=server_id, wantAck=True)
```

## Migration Steps

### Phase 1: Preparation (No Downtime)

1. **Backup Current System**
   ```bash
   # On each Raspberry Pi
   cd /home/pi
   tar -czf iqright_backup_$(date +%Y%m%d).tar.gz IQRight_Local/
   ```

2. **Update Code Repository**
   ```bash
   cd ~/IQRight_Local
   git pull  # or copy new files
   ```

3. **Install Python Dependencies**
   ```bash
   pip3 install meshtastic pypubsub
   ```

### Phase 2: Server Setup

4. **Install Meshtastic on Server**
   ```bash
   # Add repository
   curl -fsSL https://download.opensuse.org/repositories/home:/meshtastic:/meshtastic/Raspbian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_meshtastic_meshtastic.gpg > /dev/null
   echo 'deb http://download.opensuse.org/repositories/home:/meshtastic:/meshtastic/Raspbian_12/ /' | sudo tee /etc/apt/sources.list.d/meshtastic.list

   sudo apt update
   sudo apt install -y meshtasticd
   ```

5. **Configure Server Node**
   ```bash
   sudo mkdir -p /etc/meshtasticd/config.d
   sudo nano /etc/meshtasticd/config.d/config.yaml
   ```

   Copy the server configuration from `MESHTASTIC_QUICKSTART.md`.

6. **Update Server Config**
   ```bash
   nano ~/IQRight_Local/utils/config.py
   ```

   Verify:
   ```python
   MESHTASTIC_SERVER_NODE_ID = 1
   MESHTASTIC_SERVER_HOST = 'localhost'
   ```

7. **Test Server**
   ```bash
   # Start meshtasticd
   sudo systemctl start meshtasticd

   # Verify
   meshtastic --host localhost --info

   # Test application
   python3 ~/IQRight_Local/CaptureMeshstatic.py
   ```

### Phase 3: Client Setup (One at a Time)

8. **Install Meshtastic on First Client**
   ```bash
   # Same as step 4
   sudo apt install -y meshtasticd
   ```

9. **Configure Client Node**
   ```bash
   sudo mkdir -p /etc/meshtasticd/config.d
   sudo nano /etc/meshtasticd/config.d/config.yaml
   ```

   Copy client configuration, setting `NodeId: 102`.

10. **Update Client Config**
    ```bash
    nano ~/IQRight_Local/utils/config.py
    ```

    Set:
    ```python
    MESHTASTIC_CLIENT_NODE_ID = 102  # Unique per device
    MESHTASTIC_SERVER_NODE_ID = 1
    ```

11. **Test Client**
    ```bash
    # Start daemon
    sudo systemctl start meshtasticd

    # Verify
    meshtastic --host localhost --info
    meshtastic --host localhost --nodes  # Should see server

    # Test application
    python3 ~/IQRight_Local/scanner_meshstatic.py
    ```

12. **Repeat for Additional Clients**
    - Increment `NodeId` for each (103, 104, etc.)
    - Update `MESHTASTIC_CLIENT_NODE_ID` accordingly

### Phase 4: Add Repeaters (Optional)

13. **Flash ESP32 Repeaters**
    - Visit https://flasher.meshtastic.org/
    - Flash firmware
    - Configure as ROUTER role
    - Set Node IDs 200+

14. **Deploy Repeaters**
    - Place midway between server and clients
    - Elevate for better range
    - Verify mesh connectivity

### Phase 5: Cutover

15. **Stop Old Services**
    ```bash
    # On server
    sudo systemctl stop iqright-lora-server  # if configured
    # or manually stop CaptureLora.py

    # On clients
    # Stop scanner_queue.py
    ```

16. **Start New Services**
    ```bash
    # On server
    sudo systemctl enable meshtasticd
    sudo systemctl start meshtasticd
    python3 ~/IQRight_Local/CaptureMeshstatic.py

    # On clients
    sudo systemctl enable meshtasticd
    sudo systemctl start meshtasticd
    python3 ~/IQRight_Local/scanner_meshstatic.py
    ```

17. **Verify End-to-End**
    - Scan QR code on client
    - Verify server receives and processes
    - Check MQTT messages published
    - Verify GUI updates on client

### Phase 6: Production Deployment

18. **Create Systemd Services**

    Server: `/etc/systemd/system/iqright-server.service`
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

    Client: `/etc/systemd/system/iqright-scanner.service`
    ```ini
    [Unit]
    Description=IQRight Meshtastic Scanner
    After=network.target meshtasticd.service graphical.target
    Requires=meshtasticd.service

    [Service]
    Type=simple
    User=pi
    WorkingDirectory=/home/pi/IQRight_Local
    Environment=DISPLAY=:0
    ExecStart=/usr/bin/python3 /home/pi/IQRight_Local/scanner_meshstatic.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=graphical.target
    ```

19. **Enable Services**
    ```bash
    sudo systemctl enable iqright-server  # on server
    sudo systemctl enable iqright-scanner # on clients
    ```

20. **Monitor and Validate**
    ```bash
    # Check services
    sudo systemctl status meshtasticd
    sudo systemctl status iqright-server

    # Monitor logs
    sudo journalctl -u meshtasticd -f
    tail -f ~/IQRight_Local/log/IQRight_Daemon.debug

    # Check mesh
    meshtastic --host localhost --nodes
    ```

## Rollback Plan

If issues occur, you can quickly revert:

1. **Stop New Services**
   ```bash
   sudo systemctl stop iqright-server
   sudo systemctl stop meshtasticd
   ```

2. **Restore Old Code** (if needed)
   ```bash
   tar -xzf ~/iqright_backup_YYYYMMDD.tar.gz
   ```

3. **Start Old Services**
   ```bash
   python3 ~/IQRight_Local/CaptureLora.py
   python3 ~/IQRight_Local/scanner_queue.py
   ```

## Validation Checklist

- [ ] Server meshtasticd running
- [ ] All clients meshtasticd running
- [ ] Mesh shows all nodes (`meshtastic --host localhost --nodes`)
- [ ] QR scans reach server
- [ ] Server lookups work (API and local)
- [ ] Responses reach clients
- [ ] GUI updates correctly
- [ ] MQTT messages published
- [ ] Commands work (break, release, undo)
- [ ] Logs show no errors
- [ ] Range is adequate (add repeaters if not)

## Common Migration Issues

### Issue: SPI Not Available
**Symptom**: `meshtasticd` fails to start, "SPI device not found"

**Solution**:
```bash
# Enable SPI
sudo raspi-config
# Interface Options -> SPI -> Enable

# Or edit config.txt
echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

### Issue: Wrong GPIO Pins
**Symptom**: Radio initialization fails

**Solution**: Verify SX1262 HAT pin configuration in `/etc/meshtasticd/config.d/config.yaml`:
```yaml
Lora:
  CS: 21      # Chip Select
  IRQ: 16     # Interrupt
  Busy: 20    # Busy signal
  Reset: 18   # Reset pin
```

For Raspberry Pi 5, add: `gpiochip: 4`

### Issue: TCP Connection Failed
**Symptom**: Python app can't connect to meshtasticd

**Solution**:
```bash
# Check daemon is listening
sudo netstat -tlnp | grep 4403

# Check config has TCP enabled
grep -A2 "Network:" /etc/meshtasticd/config.d/config.yaml

# Should show:
#   TCPEnabled: true
#   TCPPort: 4403
```

### Issue: Node Not Visible in Mesh
**Symptom**: `meshtastic --nodes` doesn't show expected nodes

**Solution**:
- Verify all nodes use same **Region** (US, EU_868, etc.)
- Check all nodes use same **ModemPreset**
- Ensure nodes are within range
- Wait 2-3 minutes for mesh discovery
- Check logs: `sudo journalctl -u meshtasticd -f`

### Issue: High Latency
**Symptom**: Messages take >10 seconds

**Solution**:
- Check number of hops: `meshtastic --host localhost --nodes` shows route
- Reduce hops by adding repeaters
- Try faster preset: `ModemPreset: MEDIUM_FAST`
- Check for interference (WiFi, metal barriers)

## Performance Comparison

Expected improvements with Meshtastic:

| Metric | LoRa | Meshtastic |
|--------|------|------------|
| **Range** | 500m-1km | 2-5km per hop |
| **Reliability** | 85-90% | 95%+ |
| **Scalability** | 3-4 clients | 10+ clients |
| **Setup Complexity** | Low | Medium |
| **Maintenance** | Manual | Automatic |
| **Community** | Limited | Very Active |

## Next Steps After Migration

1. **Optimize Mesh**
   - Adjust repeater locations for best coverage
   - Fine-tune modem preset for range vs. speed
   - Monitor RSSI/SNR values

2. **Security**
   - Enable encryption
   - Set channel keys
   - Restrict node joining

3. **Monitoring**
   - Set up Grafana dashboards for mesh health
   - Create alerts for node failures
   - Track message delivery rates

4. **Documentation**
   - Document final node IDs
   - Map physical locations
   - Create runbooks for common issues

## Support

For issues during migration:
1. Check logs: `sudo journalctl -u meshtasticd -f`
2. Verify config: `cat /etc/meshtasticd/config.d/config.yaml`
3. Test connectivity: `meshtastic --host localhost --info`
4. Consult: `MESHTASTIC_SETUP.md` and `MESHTASTIC_QUICKSTART.md`
5. Community: https://meshtastic.discourse.group/

## File Reference

| Purpose | Old File | New File |
|---------|----------|----------|
| Server | `CaptureLora.py` | `CaptureMeshstatic.py` |
| Client | `scanner_queue.py` | `scanner_meshstatic.py` |
| Config | `utils/config.py` | Same (updated) |
| Daemon Config | N/A | `/etc/meshtasticd/config.d/config.yaml` |

Both old and new files will coexist in the repository for fallback purposes.
